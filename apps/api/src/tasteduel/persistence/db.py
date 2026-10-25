"""Lazy connections and transaction-local ownership scope; no create_all."""

from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from tasteduel.config import validate_local_url


def local_engine(url: str, *, migration: bool = False) -> Engine:
    validate_local_url(url, migration=migration)
    return create_engine(
        url,
        hide_parameters=True,
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=1,
        connect_args={"connect_timeout": 3, "application_name": "tasteduel-foundation"},
    )


@contextmanager
def scoped_session(engine: Engine, session_id: UUID):
    with Session(engine, expire_on_commit=False) as db, db.begin():
        db.execute(text("SELECT set_config('app.session_id', :owner, true)"), {"owner": str(session_id)})
        yield db
