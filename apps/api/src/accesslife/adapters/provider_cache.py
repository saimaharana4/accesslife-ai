from datetime import timedelta
from sqlalchemy.dialects.postgresql import insert
from accesslife.persistence.db import Session, ProviderCacheRow, now


def get(key):
    with Session() as db:
        row = db.get(ProviderCacheRow, key)
        return row.payload if row and row.expires_at > now() else None


def put(key, payload):
    with Session.begin() as db:
        db.execute(
            insert(ProviderCacheRow)
            .values(id=key, payload=payload, expires_at=now() + timedelta(hours=1))
            .on_conflict_do_update(
                index_elements=[ProviderCacheRow.id],
                set_={"payload": payload, "expires_at": now() + timedelta(hours=1)},
            )
        )
