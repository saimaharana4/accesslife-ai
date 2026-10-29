"""Explicit guest-selected discoveries. Prediction correctness is never an input.

The session row serializes save, unsave and clear operations across instances.
No provider, ranking, score or inferred preference is written by this service.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, text

from tasteduel.application.errors import AppError, not_found
from tasteduel.application.event_accounting import record
from tasteduel.persistence import models as m
from tasteduel.persistence.db import scoped_session


def discovery_expiry(db, owner, entity, session):
    """Only an accepted, already-delivered comparison grants discovery eligibility.

    Both revealed contestants are eligible; neither the submitted guess nor its
    correctness is a preference signal. Use the earliest supporting context expiry
    conservatively, without extending the immutable metadata retention period.
    """
    contexts = list(
        db.execute(
            select(m.Game.id, m.Game.expires_at, m.RankingSnapshot.expires_at)
            .select_from(m.RoundContestant)
            .join(m.Answer, m.Answer.round_id == m.RoundContestant.round_id)
            .join(m.DeliveredRound, m.DeliveredRound.id == m.RoundContestant.round_id)
            .join(m.PrivatePair, m.PrivatePair.id == m.DeliveredRound.pair_id)
            .join(m.RankingSnapshot, m.RankingSnapshot.id == m.PrivatePair.snapshot_id)
            .join(m.Game, m.Game.id == m.RoundContestant.game_id)
            .where(
                m.RoundContestant.session_id == owner,
                m.RoundContestant.entity_id == entity.id,
                m.Answer.session_id == owner,
                m.Game.session_id == owner,
                m.RankingSnapshot.session_id == owner,
            )
        )
    )
    # A replay loses its evidence capability when its creator revokes sharing.
    # An independent accepted solo context can still support the explicit save.
    from tasteduel.application.challenges import require_replay_active

    retained = []
    for game_id, game_expiry, snapshot_expiry in contexts:
        try:
            require_replay_active(db, game_id)
        except AppError:
            continue
        retained.extend((game_expiry, snapshot_expiry))
    if not retained:
        return None
    return min(session.expires_at, entity.expires_at, *retained)


@dataclass(frozen=True)
class SavedDiscovery:
    entity_id: UUID
    created: bool


class DiscoveryService:
    def __init__(self, engine):
        self.engine = engine

    def _session(self, db, owner):
        row = db.scalar(select(m.Session).where(m.Session.id == owner).with_for_update())
        now = db.scalar(select(text("clock_timestamp()")))
        if row is None or row.revoked_at is not None or row.expires_at <= now or not db.scalar(
            select(text("tasteduel.session_live(:owner)")).params(owner=owner)
        ):
            raise AppError(401, "SESSION_REQUIRED", "An active guest session is required.")
        return row, now

    def save(self, owner, entity_id, idempotency_key):
        digest = sha256(
            json.dumps({"entity_id": str(entity_id)}, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        with scoped_session(self.engine, owner) as db:
            session, now = self._session(db, owner)
            prior = db.scalar(
                select(m.MutationReceipt).where(
                    m.MutationReceipt.session_id == owner,
                    m.MutationReceipt.operation == "save_discovery",
                    m.MutationReceipt.idempotency_key == idempotency_key,
                )
            )
            if prior is not None and prior.signature_hash != digest:
                raise AppError(409, "IDEMPOTENCY_CONFLICT", "This key belongs to a different discovery.")
            entity = db.scalar(select(m.Entity).where(m.Entity.id == entity_id, m.Entity.session_id == owner))
            if entity is None:
                raise not_found()
            expiry = discovery_expiry(db, owner, entity, session)
            if expiry is None:
                raise not_found()
            if expiry <= now:
                raise AppError(410, "DISCOVERY_EXPIRED", "This discovery's supporting evidence has expired.")
            row = db.scalar(
                select(m.Discovery).where(m.Discovery.session_id == owner, m.Discovery.entity_id == entity_id)
            )
            if prior is not None:
                if row is None or row.id != prior.outcome_id:
                    raise AppError(
                        409,
                        "DISCOVERY_REMOVED",
                        "This save was removed. Use a new save action to save it again.",
                    )
                return SavedDiscovery(entity_id, False)
            created = row is None
            if row is None:
                # Bound retained explicit signals, including expired rows. Unsave
                # permits deliberate removal rather than silent background loss.
                count = db.scalar(
                    select(func.count()).select_from(m.Discovery).where(m.Discovery.session_id == owner)
                )
                if count >= 100:
                    raise AppError(409, "DISCOVERY_LIMIT", "Remove a saved discovery before saving another.")
                row = m.Discovery(id=uuid4(), session_id=owner, entity_id=entity_id)
                db.add(row)
                db.flush()
            db.add(
                m.MutationReceipt(
                    id=uuid4(),
                    session_id=owner,
                    operation="save_discovery",
                    idempotency_key=idempotency_key,
                    signature_hash=digest,
                    subject_kind="entity",
                    subject_id=entity_id,
                    outcome_kind="discovery",
                    outcome_id=row.id,
                    outcome_revision=0,
                    status="completed",
                    expires_at=expiry,
                )
            )
            db.flush()
            if created:
                supporting_game = db.scalar(
                    select(m.RoundContestant.game_id)
                    .join(m.Answer, m.Answer.round_id == m.RoundContestant.round_id)
                    .where(m.RoundContestant.session_id == owner, m.RoundContestant.entity_id == entity_id)
                    .order_by(m.Answer.created_at.desc())
                    .limit(1)
                )
                record(db, owner=owner, game_id=supporting_game, event="discovery_saved", subject_id=row.id)
            return SavedDiscovery(entity_id, created)

    def remove(self, owner, entity_id):
        with scoped_session(self.engine, owner) as db:
            self._session(db, owner)
            # A missing/foreign ID has the same successful no-op result. Never
            # reveal whether another guest saved this ID; do not resurrect on retry.
            db.execute(
                delete(m.Discovery).where(m.Discovery.session_id == owner, m.Discovery.entity_id == entity_id)
            )
