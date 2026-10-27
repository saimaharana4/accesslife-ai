"""Private, first-party execution facts; never a preference or human-impact metric.

There is deliberately no browser event endpoint and no arbitrary metadata field.
Events commit with the authoritative mutation; retries reuse the semantic subject.
"""

import os
from datetime import timedelta

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert

from tasteduel.persistence import models as m

EVENTS = frozenset({
    "game_started", "game_completed", "round_answered", "replay",
    "challenge_create", "challenge_open", "challenge_complete", "discovery_saved",
})
RETENTION_DAYS = 7


def record(db, *, owner, game_id, event, subject_id):
    """Subject is an internal game/round/challenge/discovery UUID, never a seed ID.

    Default/test deployments and fixture games cannot enter production denominators.
    Mode must be opted into by the deployment operator, not a request header.
    """
    if event not in EVENTS:
        raise ValueError("unsupported accounting event")
    receipt = db.scalar(select(m.CurationReceipt).where(m.CurationReceipt.game_id == game_id))
    mode = "fixture" if receipt is None or receipt.curator_mode == "fixture" else "qloo"
    cohort = "operational" if os.getenv("TASTEDUEL_EVENT_COHORT") == "operational" else "excluded"
    now = db.scalar(select(text("clock_timestamp()")))
    # Bounded to this owner's short-lived rows under forced RLS. A privileged
    # scheduled purge remains an explicit production operation, not a hidden job.
    db.execute(delete(m.ProductEvent).where(m.ProductEvent.expires_at <= now))
    db.execute(
        insert(m.ProductEvent).values(
            session_id=owner, game_id=game_id, subject_id=subject_id,
            event=event, source_mode=mode, cohort=cohort,
            expires_at=now + timedelta(days=RETENTION_DAYS),
        ).on_conflict_do_nothing(constraint="uq_product_events_session_event_subject")
    )
