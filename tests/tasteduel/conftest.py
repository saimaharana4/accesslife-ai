"""Dedicated fixtures. Run with --confcutdir=tests/tasteduel; no AccessLife imports."""

from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
import hashlib
import os
import secrets
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest

from tasteduel.api.main import create_app
from tasteduel.config import Settings
from tasteduel.persistence.db import local_engine, scoped_session
from tasteduel.persistence.models import Session


@pytest.fixture
def expired_guest_cookie(db_engine):
    """Insert an expired synthetic identity; never rewrite immutable session TTLs."""
    owner = uuid4()
    token = f"{owner}.{secrets.token_urlsafe(32)}"
    now = datetime.now(UTC)
    with scoped_session(db_engine, owner) as db:
        db.add(
            Session(
                id=owner,
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
                created_at=now - timedelta(days=2),
                expires_at=now - timedelta(days=1),
            )
        )
    return token


@pytest.fixture(scope="session")
def db_engine():
    value = os.environ.get("TASTEDUEL_TEST_DATABASE_URL")
    if not value:
        pytest.fail(
            "Run database checks through scripts/tasteduel_local.py test; no legacy URL fallback is allowed."
        )
    engine = local_engine(value)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def db_owner_engine():
    value = os.environ.get("TASTEDUEL_TEST_MIGRATION_DATABASE_URL")
    if not value:
        pytest.fail("A separate dedicated migration-owner test connection is required.")
    engine = local_engine(value, migration=True)
    yield engine
    engine.dispose()


@pytest.fixture
def api_client(db_engine):
    app = create_app(Settings(cookie_secure=True, allowed_origins=("https://testserver",)), engine=db_engine)
    with TestClient(
        app,
        base_url="https://testserver",
        headers={"Origin": "https://testserver"},
        raise_server_exceptions=False,
    ) as client:
        yield client


@pytest.fixture
def create_guest(db_engine):
    app = create_app(Settings(cookie_secure=True, allowed_origins=("https://testserver",)), engine=db_engine)
    with ExitStack() as stack:

        def create():
            client = stack.enter_context(
                TestClient(
                    app,
                    base_url="https://testserver",
                    headers={"Origin": "https://testserver"},
                    raise_server_exceptions=False,
                )
            )
            response = client.post("/v1/sessions", json={})
            assert response.status_code == 201, "Guest creation failed; no sensitive response is logged."
            owner = UUID(client.cookies.get("tasteduel_session").split(".", 1)[0])
            return client, owner

        yield create
