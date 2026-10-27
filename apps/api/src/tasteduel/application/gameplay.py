"""Transactional gameplay. Generation runs outside transactions in the awaited caller.

Session -> reservation/game is the universal lock order. All capabilities returned
here are private Python values; HTTP responses require explicit projections.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from hashlib import sha256
import json
import secrets
from uuid import UUID, uuid4

from sqlalchemy import select, text

from tasteduel.application.errors import AppError, not_found
from tasteduel.application.event_accounting import record
from tasteduel.domain.curation import CurationReceipt as ReceiptValue
from tasteduel.domain.adaptive import (
    SELECTION_VERSION,
    InsufficientContinuation,
    PerformanceRound,
    SelectionPair,
    choose_next,
)
from tasteduel.persistence import models as m
from tasteduel.persistence.db import scoped_session
from tasteduel.ports.qloo import EntityMetadata


@dataclass(frozen=True)
class GenerationClaim:
    reservation_id: UUID
    game_id: UUID
    session_id: UUID
    lease_owner: UUID
    fence: int
    lease_expires_at: datetime
    seed: EntityMetadata


@dataclass(frozen=True)
class GenerationObservation:
    game_id: UUID
    status: str
    lease_expires_at: datetime | None


@dataclass(frozen=True)
class MutationOutcome:
    game_id: UUID
    round_id: UUID
    revision: int


def signature(**value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def conflict(code="STATE_CONFLICT"):
    return AppError(409, code, "This request conflicts with the saved game state.")


class GameplayService:
    def __init__(self, engine, *, lease_seconds=30):
        if not 25 <= lease_seconds <= 60:
            raise ValueError("lease must cover bounded generation and commit")
        self.engine, self.lease_seconds = engine, lease_seconds

    def _session(self, db, session_id):
        row = db.scalar(select(m.Session).where(m.Session.id == session_id).with_for_update())
        now = db.scalar(select(text("clock_timestamp()")))
        if row is None or row.revoked_at is not None or row.expires_at <= now:
            raise AppError(401, "SESSION_REQUIRED", "An active guest session is required.")
        return row, now

    def _game(self, db, session_id, game_id, now):
        from tasteduel.application.challenges import require_replay_active

        game = db.scalar(
            select(m.Game).where(m.Game.id == game_id, m.Game.session_id == session_id).with_for_update()
        )
        if game is None:
            raise not_found()
        require_replay_active(db, game_id)
        if game.expires_at <= now or game.status == "expired":
            raise AppError(410, "GAME_EXPIRED", "This game and its supporting evidence have expired.")
        if game.status == "cancelled":
            raise conflict()
        return game

    def reserve(self, session_id, *, seed_entity_id, seed_type, mode="solo", idempotency_key):
        if mode != "solo" or seed_type not in ("artist", "movie"):
            raise AppError(422, "INVALID_GAME", "Choose a supported seed and solo mode.")
        input_hash = signature(seed_entity_id=seed_entity_id, seed_type=seed_type, mode=mode)
        with scoped_session(self.engine, session_id) as db:
            session, now = self._session(db, session_id)
            row = db.scalar(
                select(m.GenerationReservation)
                .where(
                    m.GenerationReservation.session_id == session_id,
                    m.GenerationReservation.operation == "create_game",
                    m.GenerationReservation.idempotency_key == idempotency_key,
                )
                .with_for_update()
            )
            if row is not None:
                if row.input_hash != input_hash:
                    raise conflict("IDEMPOTENCY_CONFLICT")
                game = self._game(db, session_id, row.game_id, now)
                if row.status == "succeeded":
                    return GenerationObservation(game.id, "succeeded", None)
                if row.status == "cancelled":
                    raise conflict("GENERATION_CANCELLED")
                if row.status == "running" and row.lease_expires_at > now:
                    return GenerationObservation(game.id, "running", row.lease_expires_at)
                if row.attempt_count >= 3:
                    raise AppError(
                        503,
                        "GENERATION_ATTEMPTS_EXHAUSTED",
                        "Start a fresh game after repeated interrupted generation.",
                    )
            entity = db.scalar(
                select(m.Entity).where(
                    m.Entity.id == seed_entity_id,
                    m.Entity.session_id == session_id,
                    m.Entity.entity_type == seed_type,
                )
            )
            if entity is None:
                raise not_found()
            if entity.expires_at <= now:
                raise AppError(410, "SEED_EXPIRED", "Search again to refresh this seed.")
            if row is None:
                game = m.Game(
                    id=uuid4(),
                    session_id=session_id,
                    seed_entity_id=entity.id,
                    seed_type=seed_type,
                    mode=mode,
                    status="preparing",
                    current_ordinal=0,
                    revision=0,
                    scoring_version="duel-score-v1",
                    validator_version="duel-pool-v1",
                    selection_version=SELECTION_VERSION,
                    selection_seed=secrets.token_hex(32),
                    expires_at=min(session.expires_at, entity.expires_at, now + timedelta(hours=24)),
                )
                db.add(game)
                db.flush()
                row = m.GenerationReservation(
                    id=uuid4(),
                    session_id=session_id,
                    game_id=game.id,
                    operation="create_game",
                    idempotency_key=idempotency_key,
                    input_hash=input_hash,
                    status="reserved",
                    fence=0,
                    attempt_count=0,
                    qloo_request_count=0,
                    model_request_count=0,
                    deadline_at=now + timedelta(seconds=20),
                )
                db.add(row)
                db.flush()
            row.status = "running"
            row.lease_owner = uuid4()
            row.lease_expires_at = now + timedelta(seconds=self.lease_seconds)
            row.deadline_at = now + timedelta(seconds=20)
            row.fence += 1
            row.attempt_count += 1
            row.failure_code = None
            db.flush()
            return GenerationClaim(
                row.id,
                game.id,
                session_id,
                row.lease_owner,
                row.fence,
                row.lease_expires_at,
                EntityMetadata(UUID(entity.provider_entity_id), entity.name, entity.entity_type),
            )

    def status(self, session_id, game_id):
        with scoped_session(self.engine, session_id) as db:
            _, now = self._session(db, session_id)
            self._game(db, session_id, game_id, now)
            row = db.scalar(
                select(m.GenerationReservation).where(
                    m.GenerationReservation.session_id == session_id,
                    m.GenerationReservation.game_id == game_id,
                )
            )
            if row is None:
                return None
            active = (
                row.status == "running" and row.lease_expires_at is not None and row.lease_expires_at > now
            )
            status = (
                "exhausted"
                if row.attempt_count >= 3 and row.status != "succeeded" and not active
                else row.status
            )
            return GenerationObservation(game_id, status, row.lease_expires_at)

    def _claim(self, db, claim, now):
        row = db.scalar(
            select(m.GenerationReservation)
            .where(
                m.GenerationReservation.id == claim.reservation_id,
                m.GenerationReservation.session_id == claim.session_id,
                m.GenerationReservation.game_id == claim.game_id,
            )
            .with_for_update()
        )
        if (
            row is None
            or row.status != "running"
            or row.fence != claim.fence
            or row.lease_owner != claim.lease_owner
            or row.lease_expires_at <= now
        ):
            raise conflict("GENERATION_CLAIM_EXPIRED")
        return row

    def fail(self, claim, safe_code="GENERATION_FAILED"):
        with scoped_session(self.engine, claim.session_id) as db:
            _, now = self._session(db, claim.session_id)
            row = self._claim(db, claim, now)
            row.status = "failed"
            row.failure_code = "GENERATION_FAILED"  # Do not persist arbitrary provider diagnostics.
            row.lease_owner = row.lease_expires_at = None

    def publish(self, claim, outcome):
        receipt = ReceiptValue.model_validate_json(outcome.receipt.model_dump_json())
        pool = outcome.pool
        if (
            receipt.game_id != claim.game_id
            or receipt.seed_entity_id != claim.seed.id
            or receipt.seed_type != claim.seed.domain
            or receipt.status != "succeeded"
            or pool is None
            or pool.status != "ready"
            or len(pool.path) != 5
            or not pool.evaluation.complete_path
            or receipt.validator_version != pool.policy.version
            or (
                receipt.policy_fingerprint is not None
                and receipt.policy_fingerprint != pool.policy.fingerprint
            )
        ):
            raise AppError(
                503, "INVALID_GENERATION", "Generation did not produce a validated five-round game."
            )
        prepared = outcome.prepared
        snapshot = getattr(prepared, "snapshot", None)
        if snapshot is None and receipt.curator_mode != "fixture":
            raise AppError(503, "INVALID_GENERATION", "A normalized evidence snapshot is required.")
        if receipt.curator_mode != "fixture" and (
            receipt.policy_fingerprint != pool.policy.fingerprint
            or receipt.policy_configuration is None
            or receipt.policy_configuration.model_dump() != asdict(pool.policy)
            or receipt.final_pool_status != "ready"
            or receipt.final_feedback is None
            or not receipt.final_feedback.five_round_path_verified
            or receipt.harness_version != "0.1.26"
        ):
            raise AppError(
                503, "INVALID_GENERATION", "Generation receipt lacks validated execution evidence."
            )
        with scoped_session(self.engine, claim.session_id) as db:
            _, now = self._session(db, claim.session_id)
            reservation = self._claim(db, claim, now)
            if reservation.deadline_at <= now:
                raise conflict("GENERATION_DEADLINE_EXCEEDED")
            game = self._game(db, claim.session_id, claim.game_id, now)
            if game.current_ordinal != 0 or game.status != "preparing":
                raise conflict()
            seed_row = db.scalar(
                select(m.Entity).where(
                    m.Entity.id == game.seed_entity_id, m.Entity.session_id == claim.session_id
                )
            )
            if seed_row is None or seed_row.provider_entity_id != str(claim.seed.id):
                raise conflict("GENERATION_CONTEXT_CONFLICT")
            observed = getattr(prepared, "observed_at", None) or (
                receipt.created_at if receipt.curator_mode == "fixture" else None
            )
            expiry = getattr(prepared, "evidence_expires_at", None) or (
                game.expires_at if receipt.curator_mode == "fixture" else None
            )
            if (
                not isinstance(observed, datetime)
                or not isinstance(expiry, datetime)
                or observed.tzinfo is None
                or expiry.tzinfo is None
                or observed.utcoffset() is None
                or expiry.utcoffset() is None
                or observed > now
                or expiry <= now
                or expiry > observed + timedelta(hours=24)
                or now - observed > timedelta(hours=1)
            ):
                raise AppError(503, "INVALID_GENERATION", "Generation evidence is missing or expired.")
            expiry = min(expiry, game.expires_at)
            candidates = {
                candidate.id: candidate for pair in pool.pairs for candidate in (pair.first, pair.second)
            }
            if snapshot is not None:
                if (
                    snapshot.seed_id != claim.seed.id
                    or snapshot.context_hash != pool.evaluation.context_hash
                    or snapshot.domain != pool.evaluation.domain
                    or snapshot.seed_domain != claim.seed.domain
                    or not snapshot.ordering_verified
                    or snapshot.provider != ("fixture" if receipt.curator_mode == "fixture" else "qloo")
                    or snapshot.score_field != "query.affinity"
                ):
                    raise AppError(
                        503, "INVALID_GENERATION", "Generation context does not match its validated pool."
                    )
                source_candidates = {candidate.id: candidate for candidate in snapshot.candidates}
                if any(
                    source_candidates.get(identifier) != candidate
                    for identifier, candidate in candidates.items()
                ):
                    raise AppError(
                        503, "INVALID_GENERATION", "Pool candidates differ from normalized evidence."
                    )
            entity_ids = {}
            source = "fixture" if receipt.curator_mode == "fixture" else "qloo"
            existing = {
                entity.provider_entity_id: entity
                for entity in db.scalars(
                    select(m.Entity).where(
                        m.Entity.session_id == claim.session_id,
                        m.Entity.provider == source,
                        m.Entity.provider_entity_id.in_([str(identifier) for identifier in candidates]),
                    )
                )
            }
            # Existing immutable metadata bounds the next game's lifetime too.
            # Never extend retained evidence just because generation was retried.
            expiry = min([expiry, *(entity.expires_at for entity in existing.values())])
            if expiry <= now:
                raise AppError(503, "INVALID_GENERATION", "Candidate metadata requires refresh.")
            if expiry < game.expires_at:
                game.expires_at = expiry
                game.revision += 1
                db.flush()
            for candidate in candidates.values():
                entity = existing.get(str(candidate.id))
                if entity is None:
                    entity = m.Entity(
                        id=uuid4(),
                        session_id=claim.session_id,
                        entity_type=candidate.domain,
                        name=candidate.name,
                        provider=source,
                        provider_entity_id=str(candidate.id),
                        attribution="Synthetic fixture" if source == "fixture" else "Qloo",
                        rights_policy="synthetic_fixture" if source == "fixture" else "private_evidence_24h",
                        artwork_asset_id=None,
                        expires_at=expiry,
                    )
                    db.add(entity)
                    db.flush()
                if (
                    entity.entity_type != candidate.domain
                    or entity.name != candidate.name
                    or entity.expires_at < expiry
                ):
                    raise AppError(503, "INVALID_GENERATION", "Candidate metadata requires refresh.")
                entity_ids[candidate.id] = entity.id
            snapshot_id = uuid4()
            db.add(
                m.RankingSnapshot(
                    id=snapshot_id,
                    session_id=claim.session_id,
                    game_id=game.id,
                    target_type=pool.evaluation.domain,
                    query_context_hash=pool.evaluation.context_hash,
                    provider_version=receipt.provider_version,
                    harness_version=receipt.harness_version,
                    score_semantics="query.affinity; same-query strict ordering only",
                    attribution="Synthetic fixture" if source == "fixture" else "Qloo",
                    rights_policy="synthetic_fixture" if source == "fixture" else "private_evidence_24h",
                    expires_at=expiry,
                    created_at=observed,
                )
            )
            db.flush()
            for candidate in candidates.values():
                db.add(
                    m.SnapshotCandidate(
                        id=uuid4(),
                        session_id=claim.session_id,
                        snapshot_id=snapshot_id,
                        entity_id=entity_ids[candidate.id],
                        entity_type=candidate.domain,
                        rank=candidate.position,
                        affinity=candidate.affinity,
                    )
                )
            db.flush()
            path = {pair.pair_id: (index, pair) for index, pair in enumerate(pool.path, 1)}
            for pair in pool.pairs:
                planned = path.get(pair.id)
                oriented = planned[1] if planned else None
                db.add(
                    m.PrivatePair(
                        id=uuid4(),
                        session_id=claim.session_id,
                        game_id=game.id,
                        snapshot_id=snapshot_id,
                        left_entity_id=entity_ids[oriented.left.entity.id if oriented else pair.first.id],
                        right_entity_id=entity_ids[oriented.right.entity.id if oriented else pair.second.id],
                        winner_entity_id=entity_ids[pair.winner_id],
                        difficulty=pair.band,
                        category_labels=sorted(pair.categories),
                        planned_ordinal=planned[0] if planned else None,
                        left_choice_id=oriented.left.id if oriented else None,
                        right_choice_id=oriented.right.id if oriented else None,
                    )
                )
            receipt_fields = {
                name: getattr(receipt, name)
                for name in (
                    "curator_mode",
                    "seed_type",
                    "qloo_request_count",
                    "tool_request_count",
                    "model_request_count",
                    "candidate_count_received",
                    "valid_pair_count",
                    "bounded_correction_count",
                    "five_round_path_verified",
                    "provider_version",
                    "harness_version",
                    "model_version",
                    "validator_version",
                    "elapsed_ms",
                    "status",
                    "created_at",
                )
            }
            db.add(
                m.CurationReceipt(
                    id=uuid4(),
                    session_id=claim.session_id,
                    game_id=game.id,
                    seed_entity_id=game.seed_entity_id,
                    target_domains_considered=list(receipt.target_domains_considered),
                    target_domains_selected=list(receipt.target_domains_selected),
                    rejection_counts={str(key): value for key, value in receipt.rejection_counts.items()},
                    full_receipt=receipt.model_dump(mode="json"),
                    **receipt_fields,
                )
            )
            db.flush()
            self._deliver(db, claim.session_id, game.id, 1)
            if reservation.deadline_at <= db.scalar(select(text("clock_timestamp()"))):
                raise conflict("GENERATION_DEADLINE_EXCEEDED")
            reservation.status = "succeeded"
            reservation.qloo_request_count = receipt.qloo_request_count
            reservation.model_request_count = receipt.model_request_count
            reservation.lease_owner = reservation.lease_expires_at = None
            db.flush()
            record(db, owner=claim.session_id, game_id=game.id, event="game_started", subject_id=game.id)
            return game.id

    def _deliver(self, db, session_id, game_id, ordinal):
        game = db.scalar(select(m.Game).where(m.Game.id == game_id, m.Game.session_id == session_id))
        if game.selection_version == SELECTION_VERSION:
            return self._deliver_adaptive(db, game, ordinal)
        pair = db.scalar(
            select(m.PrivatePair).where(
                m.PrivatePair.session_id == session_id,
                m.PrivatePair.game_id == game_id,
                m.PrivatePair.planned_ordinal == ordinal,
            )
        )
        if pair is None:
            raise AppError(503, "STORED_STATE_UNAVAILABLE", "The saved continuation is unavailable.")
        delivered = m.DeliveredRound(
            id=uuid4(), session_id=session_id, game_id=game_id, pair_id=pair.id, ordinal=ordinal
        )
        db.add(delivered)
        db.flush()
        db.add_all(
            [
                m.RoundContestant(
                    id=pair.left_choice_id,
                    session_id=session_id,
                    game_id=game_id,
                    round_id=delivered.id,
                    entity_id=pair.left_entity_id,
                    side="left",
                ),
                m.RoundContestant(
                    id=pair.right_choice_id,
                    session_id=session_id,
                    game_id=game_id,
                    round_id=delivered.id,
                    entity_id=pair.right_entity_id,
                    side="right",
                ),
            ]
        )
        db.flush()
        return delivered

    def _deliver_adaptive(self, db, game, ordinal):
        pairs = list(
            db.scalars(
                select(m.PrivatePair).where(
                    m.PrivatePair.session_id == game.session_id, m.PrivatePair.game_id == game.id
                )
            )
        )
        values = {
            pair.id: SelectionPair(
                pair.id,
                frozenset((pair.left_entity_id, pair.right_entity_id)),
                pair.difficulty,
                frozenset(pair.category_labels),
            )
            for pair in pairs
        }
        rows = list(
            db.execute(
                select(m.DeliveredRound, m.Answer, m.PrivatePair)
                .join(m.Answer, m.Answer.round_id == m.DeliveredRound.id)
                .join(m.PrivatePair, m.PrivatePair.id == m.DeliveredRound.pair_id)
                .where(m.DeliveredRound.game_id == game.id, m.DeliveredRound.session_id == game.session_id)
                .order_by(m.DeliveredRound.ordinal)
            )
        )
        if len(rows) != ordinal - 1:
            raise conflict("ANSWER_REQUIRED")
        history = tuple(
            PerformanceRound(
                values[pair.id],
                answer.correct,
                "left"
                if (delivered.left_entity_id or pair.left_entity_id) == pair.winner_entity_id
                else "right",
            )
            for delivered, answer, pair in rows
        )
        receipt = db.scalar(
            select(m.CurationReceipt).where(
                m.CurationReceipt.game_id == game.id, m.CurationReceipt.session_id == game.session_id
            )
        )
        policy = (receipt.full_receipt or {}).get("policy_configuration") or {}
        try:
            selection = choose_next(
                tuple(values.values()),
                history,
                selection_seed=bytes.fromhex(game.selection_seed),
                min_categories=policy.get("min_categories", 0),
                min_bands=policy.get("min_bands", 1),
            )
        except (ValueError, InsufficientContinuation) as exc:
            raise AppError(
                503, "STORED_STATE_UNAVAILABLE", "The saved valid continuation is unavailable."
            ) from exc
        pair = next(pair for pair in pairs if pair.id == selection.pair_id)
        loser = pair.right_entity_id if pair.left_entity_id == pair.winner_entity_id else pair.left_entity_id
        left, right = (
            (pair.winner_entity_id, loser)
            if selection.winner_side == "left"
            else (loser, pair.winner_entity_id)
        )
        delivered = m.DeliveredRound(
            id=uuid4(),
            session_id=game.session_id,
            game_id=game.id,
            pair_id=pair.id,
            ordinal=ordinal,
            left_entity_id=left,
            right_entity_id=right,
            selection_context={key: value for key, value in asdict(selection).items() if key != "pair_id"},
        )
        db.add(delivered)
        db.flush()
        db.add_all(
            [
                m.RoundContestant(
                    id=uuid4(),
                    session_id=game.session_id,
                    game_id=game.id,
                    round_id=delivered.id,
                    entity_id=entity_id,
                    side=side,
                )
                for side, entity_id in (("left", left), ("right", right))
            ]
        )
        db.flush()
        return delivered

    def _prior(self, db, session_id, operation, key, digest):
        row = db.scalar(
            select(m.MutationReceipt).where(
                m.MutationReceipt.session_id == session_id,
                m.MutationReceipt.operation == operation,
                m.MutationReceipt.idempotency_key == key,
            )
        )
        if row and row.signature_hash != digest:
            raise conflict("IDEMPOTENCY_CONFLICT")
        return MutationOutcome(row.subject_id, row.outcome_id, row.outcome_revision) if row else None

    def _save(self, db, game, operation, key, digest, round_id, *, revision=None):
        db.refresh(game)
        revision = game.revision if revision is None else revision
        db.add(
            m.MutationReceipt(
                id=uuid4(),
                session_id=game.session_id,
                operation=operation,
                idempotency_key=key,
                signature_hash=digest,
                subject_kind="game",
                subject_id=game.id,
                outcome_kind="round",
                outcome_id=round_id,
                outcome_revision=revision,
                status="completed",
                expires_at=game.expires_at,
            )
        )
        db.flush()
        return MutationOutcome(game.id, round_id, revision)

    def answer(self, session_id, game_id, *, round_id, choice_id, expected_revision, idempotency_key):
        digest = signature(
            game_id=game_id, round_id=round_id, choice_id=choice_id, expected_revision=expected_revision
        )
        with scoped_session(self.engine, session_id) as db:
            _, now = self._session(db, session_id)
            game = self._game(db, session_id, game_id, now)
            prior = self._prior(db, session_id, "answer", idempotency_key, digest)
            if prior:
                return prior
            delivered = db.scalar(
                select(m.DeliveredRound).where(
                    m.DeliveredRound.id == round_id,
                    m.DeliveredRound.session_id == session_id,
                    m.DeliveredRound.game_id == game_id,
                )
            )
            if delivered is None:
                raise not_found()
            accepted = db.scalar(
                select(m.Answer).where(m.Answer.round_id == round_id, m.Answer.session_id == session_id)
            )
            if accepted:
                if accepted.choice_id != choice_id:
                    raise conflict("ANSWER_CONFLICT")
                # The answer's saved revision is independent of later navigation.
                saved = db.scalar(
                    select(m.MutationReceipt)
                    .where(
                        m.MutationReceipt.operation == "answer",
                        m.MutationReceipt.session_id == session_id,
                        m.MutationReceipt.outcome_id == round_id,
                    )
                    .order_by(m.MutationReceipt.created_at)
                )
                if saved is None:
                    raise AppError(
                        503, "STORED_STATE_UNAVAILABLE", "The saved answer receipt is unavailable."
                    )
                return self._save(
                    db, game, "answer", idempotency_key, digest, round_id, revision=saved.outcome_revision
                )
            if (
                delivered.ordinal != game.current_ordinal
                or game.revision != expected_revision
                or game.status != "playing"
            ):
                raise conflict("REVISION_CONFLICT")
            choice = db.scalar(
                select(m.RoundContestant).where(
                    m.RoundContestant.id == choice_id,
                    m.RoundContestant.round_id == round_id,
                    m.RoundContestant.session_id == session_id,
                )
            )
            if choice is None:
                raise not_found()
            db.add(
                m.Answer(
                    id=uuid4(),
                    session_id=session_id,
                    game_id=game_id,
                    round_id=round_id,
                    choice_id=choice_id,
                    idempotency_key=idempotency_key,
                    correct=False,
                )
            )
            db.flush()
            record(db, owner=session_id, game_id=game_id, event="round_answered", subject_id=round_id)
            if delivered.ordinal == 5:
                score = sum(
                    db.scalars(
                        select(m.Answer.correct).where(
                            m.Answer.game_id == game_id, m.Answer.session_id == session_id
                        )
                    )
                )
                db.add(
                    m.GameResult(
                        id=uuid4(),
                        session_id=session_id,
                        game_id=game_id,
                        score=score,
                        scoring_version=game.scoring_version,
                    )
                )
                db.flush()
                record(db, owner=session_id, game_id=game_id, event="game_completed", subject_id=game_id)
                if game.mode == "fixed":
                    record(db, owner=session_id, game_id=game_id, event="challenge_complete", subject_id=game_id)
            return self._save(db, game, "answer", idempotency_key, digest, round_id)

    def advance(self, session_id, game_id, *, answered_round_id, expected_revision, idempotency_key):
        digest = signature(
            game_id=game_id, answered_round_id=answered_round_id, expected_revision=expected_revision
        )
        with scoped_session(self.engine, session_id) as db:
            _, now = self._session(db, session_id)
            game = self._game(db, session_id, game_id, now)
            prior = self._prior(db, session_id, "advance", idempotency_key, digest)
            if prior:
                return prior
            delivered = db.scalar(
                select(m.DeliveredRound).where(
                    m.DeliveredRound.id == answered_round_id,
                    m.DeliveredRound.session_id == session_id,
                    m.DeliveredRound.game_id == game_id,
                )
            )
            if delivered is None:
                raise not_found()
            accepted = db.scalar(
                select(m.Answer).where(
                    m.Answer.round_id == answered_round_id, m.Answer.session_id == session_id
                )
            )
            if accepted is None:
                raise conflict("ANSWER_REQUIRED")
            # A second tap with a new key remains the same advance, not another round.
            if delivered.ordinal < game.current_ordinal:
                saved = db.scalar(
                    select(m.MutationReceipt).where(
                        m.MutationReceipt.session_id == session_id,
                        m.MutationReceipt.operation == "advance",
                        m.MutationReceipt.subject_id == game_id,
                        m.MutationReceipt.outcome_id.in_(
                            select(m.DeliveredRound.id).where(
                                m.DeliveredRound.game_id == game_id,
                                m.DeliveredRound.ordinal == delivered.ordinal + 1,
                            )
                        ),
                    )
                )
                if saved:
                    return self._save(
                        db,
                        game,
                        "advance",
                        idempotency_key,
                        digest,
                        saved.outcome_id,
                        revision=saved.outcome_revision,
                    )
                raise conflict()
            if game.revision != expected_revision:
                raise conflict("REVISION_CONFLICT")
            if delivered.ordinal == 5:
                return self._save(db, game, "advance", idempotency_key, digest, answered_round_id)
            following = self._deliver(db, session_id, game_id, delivered.ordinal + 1)
            return self._save(db, game, "advance", idempotency_key, digest, following.id)
