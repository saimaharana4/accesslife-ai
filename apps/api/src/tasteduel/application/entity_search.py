"""Persist minimal, owned provider metadata without moving provider JSON upstream."""

from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select

from tasteduel.application.gameplay import GameplayService
from tasteduel.persistence import models as m
from tasteduel.persistence.db import scoped_session
from tasteduel.ports.reads import EntityRead


def remember_search_entities(engine, session_id, entities):
    result = []
    expired = False
    with scoped_session(engine, session_id) as db:
        owner, now = GameplayService(engine)._session(db, session_id)
        for entity in entities:
            row = db.scalar(
                select(m.Entity).where(
                    m.Entity.session_id == session_id,
                    m.Entity.provider == "qloo",
                    m.Entity.provider_entity_id == str(entity.id),
                )
            )
            if row is None:
                row = m.Entity(
                    id=uuid4(),
                    session_id=session_id,
                    entity_type=entity.domain,
                    name=entity.name,
                    provider="qloo",
                    provider_entity_id=str(entity.id),
                    attribution="Qloo Search API",
                    rights_policy="qloo_private_minimal_v1",
                    expires_at=min(owner.expires_at, now + timedelta(hours=1)),
                )
                db.add(row)
                db.flush()
            if row.expires_at <= now:
                expired = True
                continue  # Immutable metadata is not silently refreshed in place.
            result.append(EntityRead(row.id, row.name, row.entity_type, "qloo", None))
    return tuple(result), expired
