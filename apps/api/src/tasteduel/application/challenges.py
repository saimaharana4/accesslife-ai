"""Capability-scoped invitations and exact, guest-owned frozen replays.

No provider dependency. Source RLS scope is entered only after resolving the
unguessable share capability. All source reads and copying share one transaction.
"""

from hashlib import sha256
import secrets
from uuid import UUID, uuid4

from sqlalchemy import null, select, text
from sqlalchemy.orm.attributes import set_committed_value

from tasteduel.application.errors import AppError, not_found
from tasteduel.application.event_accounting import record
from tasteduel.application.gameplay import GameplayService, conflict, signature
from tasteduel.persistence import models as m
from tasteduel.persistence.db import scoped_session


def scope(db, owner):
    db.execute(text("SELECT set_config('app.session_id',:owner,true)"), {"owner": str(owner)})


def capability(db, digest):
    db.execute(text("SELECT set_config('app.challenge_hash',:digest,true)"), {"digest": digest})


def effective_deadline(db, challenge):
    if challenge is not None and db.scalar(text("SELECT to_regprocedure('tasteduel.challenge_deadline(uuid)')")) is not None:
        deadline = db.scalar(text("SELECT tasteduel.challenge_deadline(:id)"), {"id": challenge.id})
        if deadline is not None:
            set_committed_value(challenge, "expires_at", min(challenge.expires_at, deadline))


def active(challenge, now):
    if challenge is None:
        raise not_found()
    if challenge.revoked_at is not None:
        raise AppError(410, "CHALLENGE_REVOKED", "The creator cleared or revoked this challenge.")
    if challenge.expires_at <= now:
        raise AppError(410, "CHALLENGE_EXPIRED", "This challenge and its evidence have expired.")


def require_replay_active(db, game_id):
    play = db.scalar(select(m.ChallengePlay).where(m.ChallengePlay.game_id == game_id))
    if play is not None:
        capability(db, play.slug_hash or "")
        challenge = db.scalar(select(m.Challenge).where(m.Challenge.id == play.challenge_id))
        effective_deadline(db, challenge)
        active(challenge, db.scalar(select(text("clock_timestamp()"))))


def copy_values(row, **overrides):
    return {
        **{c.name: getattr(row, c.name) for c in row.__table__.columns if c.name not in {"id", "session_id"}},
        **overrides,
    }


class ChallengeService:
    def __init__(self, engine):
        self.engine = engine
        self.gameplay = GameplayService(engine)

    def _lookup(self, db, slug):
        digest = sha256(slug.encode()).hexdigest()
        capability(db, digest)
        challenge = db.scalar(select(m.Challenge).where(m.Challenge.slug_hash == digest))
        if challenge is None:
            tombstone = db.scalar(select(m.ChallengeTombstone).where(
                m.ChallengeTombstone.slug_hash == digest,
                m.ChallengeTombstone.expires_at > text("clock_timestamp()"),
            ))
            if tombstone is not None:
                raise AppError(410, "CHALLENGE_REVOKED" if tombstone.reason == "revoked" else "CHALLENGE_EXPIRED",
                               "This challenge is no longer available.")
        effective_deadline(db, challenge)
        active(challenge, db.scalar(select(text("clock_timestamp()"))))
        return challenge

    def invitation(self, slug):
        with scoped_session(self.engine, UUID(int=0)) as db:
            challenge = self._lookup(db, slug)
            scope(db, challenge.session_id)
            owner, now = self.gameplay._session(db, challenge.session_id)
            effective_deadline(db, challenge)
            active(challenge, now)
            game = db.get(m.Game, challenge.source_game_id)
            seed = db.get(m.Entity, game.seed_entity_id)
            if seed is None or seed.expires_at <= now:
                raise AppError(410, "CHALLENGE_EXPIRED", "The challenge seed evidence has expired.")
            return challenge, seed

    def create(self, owner, game_id, key):
        digest = signature(game_id=game_id)
        with scoped_session(self.engine, owner) as db:
            session, now = self.gameplay._session(db, owner)
            receipt = db.scalar(
                select(m.MutationReceipt).where(
                    m.MutationReceipt.session_id == owner,
                    m.MutationReceipt.operation == "create_challenge",
                    m.MutationReceipt.idempotency_key == key,
                )
            )
            if receipt and receipt.signature_hash != digest:
                raise conflict("IDEMPOTENCY_CONFLICT")
            game = self.gameplay._game(db, owner, game_id, now)
            if game.mode != "solo":
                raise AppError(409, "CHALLENGE_RESHARE_UNAVAILABLE", "A friend replay cannot create a detached new challenge. Create a new solo game to share.")
            if game.status != "completed":
                raise AppError(409, "GAME_INCOMPLETE", "Complete the five rounds before sharing.")
            challenge = db.scalar(select(m.Challenge).where(m.Challenge.source_game_id == game_id))
            created = challenge is None
            if challenge is None:
                result = db.scalar(select(m.GameResult).where(m.GameResult.game_id == game_id))
                evidence_entities = list(
                    db.scalars(
                        select(m.Entity).where(
                            m.Entity.id.in_(
                                select(m.RoundContestant.entity_id).where(
                                    m.RoundContestant.game_id == game_id
                                )
                            )
                        )
                    )
                )
                seed = db.get(m.Entity, game.seed_entity_id)
                snapshots = list(
                    db.scalars(
                        select(m.RankingSnapshot).where(
                            m.RankingSnapshot.id.in_(
                                select(m.PrivatePair.snapshot_id)
                                .join(m.DeliveredRound, m.DeliveredRound.pair_id == m.PrivatePair.id)
                                .where(m.DeliveredRound.game_id == game_id)
                            )
                        )
                    )
                )
                expiry = min(
                    game.expires_at,
                    session.expires_at,
                    seed.expires_at,
                    *(e.expires_at for e in evidence_entities),
                    *(s.expires_at for s in snapshots),
                )
                if expiry <= now:
                    raise AppError(410, "CHALLENGE_EXPIRED", "The delivered evidence has expired.")
                slug = secrets.token_urlsafe(32)
                challenge = m.Challenge(
                    id=uuid4(),
                    session_id=owner,
                    source_game_id=game_id,
                    share_slug=slug,
                    slug_hash=sha256(slug.encode()).hexdigest(),
                    version=1,
                    creator_score=result.score,
                    scoring_version=game.scoring_version,
                    validator_version=game.validator_version,
                    expires_at=expiry,
                )
                db.add(challenge)
                db.flush()
            effective_deadline(db, challenge)
            active(challenge, now)
            if receipt is None:
                db.add(
                    m.MutationReceipt(
                        session_id=owner,
                        operation="create_challenge",
                        idempotency_key=key,
                        signature_hash=digest,
                        subject_kind="game",
                        subject_id=game_id,
                        outcome_kind="challenge",
                        outcome_id=challenge.id,
                        outcome_revision=game.revision,
                        status="completed",
                        expires_at=challenge.expires_at,
                    )
                )
                db.flush()
            if created:
                record(db, owner=owner, game_id=game_id, event="challenge_create", subject_id=challenge.id)
            return challenge.share_slug, created

    def revoke(self, owner, slug):
        with scoped_session(self.engine, owner) as db:
            _, now = self.gameplay._session(db, owner)
            challenge = db.scalar(
                select(m.Challenge)
                .where(
                    m.Challenge.slug_hash == sha256(slug.encode()).hexdigest(),
                    m.Challenge.session_id == owner,
                )
                .with_for_update()
            )
            if challenge is None:
                raise not_found()
            if challenge.revoked_at is None:
                challenge.revoked_at = now

    def play(self, owner, slug, key):
        digest = signature(slug=slug)
        with scoped_session(self.engine, owner) as db:
            challenge = self._lookup(db, slug)
            # Globally ordered session locks also cover reciprocal A/B replays.
            sessions = {}
            for session_id in sorted({owner, challenge.session_id}, key=str):
                scope(db, session_id)
                sessions[session_id], now = self.gameplay._session(db, session_id)
            guest = sessions[owner]
            scope(db, owner)
            prior = db.scalar(
                select(m.MutationReceipt).where(
                    m.MutationReceipt.session_id == owner,
                    m.MutationReceipt.operation == "play_challenge",
                    m.MutationReceipt.idempotency_key == key,
                )
            )
            if prior and prior.signature_hash != digest:
                raise conflict("IDEMPOTENCY_CONFLICT")
            db.refresh(challenge)
            effective_deadline(db, challenge)
            active(challenge, now)
            if prior:
                return prior.outcome_id, False
            # Serialize with creator clearing/revocation. Do not grant a source
            # row to the guest or attach their game to creator-owned entities.
            scope(db, challenge.session_id)
            self.gameplay._session(db, challenge.session_id)
            db.refresh(challenge)
            effective_deadline(db, challenge)
            active(challenge, now)
            source = db.get(m.Game, challenge.source_game_id)
            rounds = list(
                db.scalars(
                    select(m.ChallengeRound)
                    .where(m.ChallengeRound.challenge_id == challenge.id)
                    .order_by(m.ChallengeRound.ordinal)
                )
            )
            ids = {
                source.seed_entity_id,
                *(r.left_entity_id for r in rounds),
                *(r.right_entity_id for r in rounds),
            }
            entities = list(db.scalars(select(m.Entity).where(m.Entity.id.in_(ids))))
            snapshots = list(
                db.scalars(
                    select(m.RankingSnapshot).where(m.RankingSnapshot.id.in_({r.snapshot_id for r in rounds}))
                )
            )
            candidates = list(
                db.scalars(
                    select(m.SnapshotCandidate).where(
                        m.SnapshotCandidate.snapshot_id.in_({r.snapshot_id for r in rounds}),
                        m.SnapshotCandidate.entity_id.in_(ids),
                    )
                )
            )
            receipt = db.scalar(select(m.CurationReceipt).where(m.CurationReceipt.game_id == source.id))
            pairs = {
                p.id: p for p in db.scalars(select(m.PrivatePair).where(m.PrivatePair.game_id == source.id))
            }
            deliveries = {
                d.id: d
                for d in db.scalars(select(m.DeliveredRound).where(m.DeliveredRound.game_id == source.id))
            }
            expiry = min(
                challenge.expires_at,
                guest.expires_at,
                *(e.expires_at for e in entities),
                *(s.expires_at for s in snapshots),
            )
            if expiry <= now or len(rounds) != 5 or len(entities) != 11:
                raise AppError(410, "CHALLENGE_EXPIRED", "This challenge no longer has retained evidence.")
            scope(db, owner)
            mapping = {}
            for entity in entities:
                existing = db.scalar(
                    select(m.Entity).where(
                        m.Entity.session_id == owner,
                        m.Entity.provider == entity.provider,
                        m.Entity.provider_entity_id == entity.provider_entity_id,
                    )
                )
                if existing is None:
                    existing = m.Entity(
                        id=uuid4(), session_id=owner, **copy_values(entity, expires_at=expiry)
                    )
                    db.add(existing)
                    db.flush()
                if existing.expires_at <= now:
                    raise AppError(410, "CHALLENGE_EXPIRED", "Retained metadata has expired in this session.")
                if any(
                    getattr(existing, field) != getattr(entity, field)
                    for field in (
                        "entity_type",
                        "name",
                        "source_url",
                        "attribution",
                        "rights_policy",
                        "artwork_asset_id",
                    )
                ):
                    raise AppError(
                        409,
                        "CHALLENGE_METADATA_CONFLICT",
                        "This session retains different metadata. Open the fixed challenge in a fresh guest session.",
                    )
                expiry = min(expiry, existing.expires_at)
                mapping[entity.id] = existing.id
            game = m.Game(
                id=uuid4(),
                session_id=owner,
                seed_entity_id=mapping[source.seed_entity_id],
                seed_type=source.seed_type,
                mode="fixed",
                status="preparing",
                current_ordinal=0,
                revision=0,
                scoring_version=challenge.scoring_version,
                validator_version=challenge.validator_version,
                selection_version="fixed-path-v1",
                selection_seed=None,
                expires_at=expiry,
            )
            db.add(game)
            db.flush()
            snapshot_map = {}
            for snapshot in snapshots:
                clone = m.RankingSnapshot(
                    id=uuid4(), session_id=owner, **copy_values(snapshot, game_id=game.id, expires_at=expiry)
                )
                db.add(clone)
                db.flush()
                snapshot_map[snapshot.id] = clone.id
            for candidate in candidates:
                db.add(
                    m.SnapshotCandidate(
                        id=uuid4(),
                        session_id=owner,
                        **copy_values(
                            candidate,
                            snapshot_id=snapshot_map[candidate.snapshot_id],
                            entity_id=mapping[candidate.entity_id],
                        ),
                    )
                )
            db.flush()
            for round_ in rounds:
                pair = pairs[deliveries[round_.source_round_id].pair_id]
                db.add(
                    m.PrivatePair(
                        id=uuid4(),
                        session_id=owner,
                        game_id=game.id,
                        snapshot_id=snapshot_map[round_.snapshot_id],
                        left_entity_id=mapping[round_.left_entity_id],
                        right_entity_id=mapping[round_.right_entity_id],
                        winner_entity_id=mapping[round_.winner_entity_id],
                        difficulty=pair.difficulty,
                        category_labels=pair.category_labels,
                        planned_ordinal=round_.ordinal,
                        left_choice_id=uuid4(),
                        right_choice_id=uuid4(),
                    )
                )
            db.flush()
            # Historical curation provenance, not a claim of new provider work.
            db.add(
                m.CurationReceipt(
                    id=uuid4(),
                    session_id=owner,
                    **copy_values(
                        receipt, game_id=game.id, seed_entity_id=game.seed_entity_id, full_receipt=null()
                    ),
                )
            )
            db.flush()
            self.gameplay._deliver(db, owner, game.id, 1)
            db.refresh(game)
            db.add(
                m.ChallengePlay(
                    session_id=owner,
                    game_id=game.id,
                    challenge_id=challenge.id,
                    slug_hash=challenge.slug_hash,
                )
            )
            db.add(
                m.MutationReceipt(
                    session_id=owner,
                    operation="play_challenge",
                    idempotency_key=key,
                    signature_hash=digest,
                    subject_kind="game",
                    subject_id=game.id,
                    outcome_kind="game",
                    outcome_id=game.id,
                    outcome_revision=game.revision,
                    status="completed",
                    expires_at=expiry,
                )
            )
            db.flush()
            for event in ("game_started", "replay", "challenge_open"):
                record(db, owner=owner, game_id=game.id, event=event, subject_id=game.id)
            return game.id, True
