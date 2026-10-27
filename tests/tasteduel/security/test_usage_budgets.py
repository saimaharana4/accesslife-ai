"""Real PostgreSQL reservations and synthetic-only provider failure boundaries."""

import asyncio
import hashlib
from uuid import uuid4
from uuid import UUID
from datetime import UTC, datetime

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text

from tasteduel.adapters.qloo_policy import AdmissionDenied, PostgresAdmissionStore
from tasteduel.adapters.usage_budget import ModelDailyBudget, UsageDenied, reserve
from tasteduel.api.main import create_app
from tasteduel.config import Settings
from tasteduel.ports.curator import ModelUnavailable
from tasteduel.persistence import models as m
from tasteduel.persistence.db import scoped_session


def random_scope():
    return hashlib.sha256(uuid4().bytes).hexdigest()


def admission(engine, scope, *, limit=2, amount=1):
    with engine.begin() as db:
        reserve(db, scope, "test-requests", limit=limit, seconds=60, amount=amount)


async def test_atomic_budget_is_shared_not_per_instance(db_engine):
    scope = random_scope()
    results = await asyncio.gather(
        *(asyncio.to_thread(admission, db_engine, scope) for _ in range(8)), return_exceptions=True
    )
    assert sum(item is None for item in results) == 2
    assert sum(isinstance(item, UsageDenied) for item in results) == 6
    with db_engine.begin() as db:
        assert db.execute(text("SELECT count(*) FROM tasteduel.usage_budgets")).scalar_one() == 0
        db.execute(text("SELECT set_config('app.usage_scope', :scope, true)"), {"scope": scope})
        row = db.execute(text("SELECT used,limit_value FROM tasteduel.usage_budgets")).one()
        assert tuple(row) == (2, 2)


def test_expiry_replaces_single_row_and_lower_limit_cannot_be_raised(db_engine, db_owner_engine):
    scope = random_scope()
    admission(db_engine, scope, limit=1)
    with pytest.raises(UsageDenied):
        admission(db_engine, scope, limit=50)
    with db_owner_engine.begin() as db:
        db.execute(text("SELECT set_config('app.usage_scope', :scope, true)"), {"scope": scope})
        db.execute(
            text(
                "UPDATE tasteduel.usage_budgets SET window_start=clock_timestamp()-interval '2 minute', expires_at=clock_timestamp()-interval '1 minute'"
            )
        )
    admission(db_engine, scope, limit=1)
    with pytest.raises(UsageDenied):
        admission(db_engine, scope, limit=1)


async def test_qloo_daily_limit_survives_new_store_and_minute_reset(db_engine, db_owner_engine):
    scope = random_scope()
    first = PostgresAdmissionStore(db_engine, requests_per_day=1)
    await first.admit(scope)
    with db_owner_engine.begin() as db:
        db.execute(text("SELECT set_config('app.provider_scope', :scope, true)"), {"scope": scope})
        db.execute(
            text(
                "UPDATE tasteduel.provider_controls SET window_start=clock_timestamp()-interval '2 minute', next_allowed_at=NULL WHERE scope_hash=:scope"
            ),
            {"scope": scope},
        )
    second = PostgresAdmissionStore(db_engine, requests_per_day=1000)
    with pytest.raises(AdmissionDenied, match="QLOO_DAILY_BUDGET_EXCEEDED"):
        await second.admit(scope)


async def test_vertex_calls_and_tokens_are_reserved_across_instances(db_engine):
    project = f"synthetic-{uuid4().hex}"
    first = ModelDailyBudget(db_engine, project=project, model="synthetic", requests=2, tokens=100)
    second = ModelDailyBudget(db_engine, project=project, model="synthetic", requests=100, tokens=1000)
    await first.admit(60)
    with pytest.raises(ModelUnavailable, match="VERTEX_DAILY_BUDGET_UNAVAILABLE"):
        await second.admit(60)
    await second.admit(40)
    with pytest.raises(ModelUnavailable):
        await second.admit(1)


async def test_exhausted_model_budget_denies_before_transport(db_engine):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from tasteduel.adapters.vertex_curator import VertexCuratorModel
    from tasteduel.agents.curator_tools import tool_schemas

    budget = ModelDailyBudget(
        db_engine, project=f"synthetic-{uuid4().hex}", model="synthetic", requests=1, tokens=10000
    )
    await budget.admit(1)
    generate = AsyncMock()
    transport = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate)))
    model = VertexCuratorModel(project="synthetic", client=transport, daily_budget=budget)
    with pytest.raises(ModelUnavailable, match="VERTEX_DAILY_BUDGET_UNAVAILABLE"):
        await model.decide(
            ({"role": "user", "data": {"confirmed_seed": {"id": "synthetic", "domain": "artist"}}},),
            tool_schemas(("movie",)),
            timeout_seconds=1,
        )
    generate.assert_not_awaited()


def test_guest_limits_ignore_forwarded_headers_and_do_not_share_nat_identity(db_engine):
    app = create_app(
        Settings(cookie_secure=True, allowed_origins=("https://testserver",), guest_searches_per_minute=1),
        engine=db_engine,
    )
    with (
        TestClient(app, base_url="https://testserver", headers={"Origin": "https://testserver"}) as first,
        TestClient(app, base_url="https://testserver", headers={"Origin": "https://testserver"}) as second,
    ):
        assert first.post("/v1/sessions", json={}).status_code == 201
        assert second.post("/v1/sessions", json={}).status_code == 201
        path = "/v1/entities/search?q=synthetic&type=artist"
        assert first.get(path).status_code == 503  # Unconfigured, still counted.
        response = first.get(path, headers={"X-Forwarded-For": "1.2.3.4", "X-Real-IP": "5.6.7.8"})
        assert response.status_code == 429
        assert response.json()["error"]["code"] == "SESSION_RATE_LIMITED"
        assert second.get(path).status_code == 503
        assert first.get("/v1/sessions/current").status_code == 200


def test_database_failure_is_sanitized_and_no_trace_or_sql_is_returned():
    from unittest.mock import Mock
    from sqlalchemy.exc import OperationalError

    engine = Mock()
    engine.begin.side_effect = OperationalError(
        "synthetic-private-sql", {}, Exception("synthetic-private-detail")
    )
    engine.connect.side_effect = OperationalError(
        "synthetic-private-sql", {}, Exception("synthetic-private-detail")
    )
    app = create_app(Settings(cookie_secure=False), engine=engine)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/v1/health/ready")
        assert response.status_code == 503
        assert "synthetic-private" not in response.text
        assert "Traceback" not in response.text


def test_unexpected_exception_is_contained_before_asgi_server_logging(caplog):
    app = create_app(Settings(cookie_secure=False))

    @app.get("/synthetic-failure")
    def fail():
        raise RuntimeError("synthetic-private-reasoning-and-secret")

    with TestClient(app) as client:
        response = client.get("/synthetic-failure")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
        assert "synthetic-private" not in response.text
    assert "synthetic-private" not in caplog.text


def test_unbounded_content_length_does_not_escape_as_integer_exception():
    app = create_app(Settings(cookie_secure=False, allowed_origins=("http://testserver",)))
    with TestClient(app) as client:
        response = client.post(
            "/v1/sessions",
            content=b"{}",
            headers={"Origin": "http://testserver", "Content-Length": "9" * 5000},
        )
        assert response.status_code == 413


async def test_body_chunk_flood_is_bounded_even_without_content_length():
    from unittest.mock import AsyncMock
    from tasteduel.api.body_limit import BoundedBodyMiddleware

    target = AsyncMock()
    received = 0
    sent = []

    async def receive():
        nonlocal received
        received += 1
        return {"type": "http.request", "body": b"", "more_body": True}

    async def send(message):
        sent.append(message)

    await BoundedBodyMiddleware(target)({"type": "http", "method": "POST"}, receive, send)
    assert received == 257
    assert sent[0]["status"] == 413
    target.assert_not_awaited()


async def test_slow_body_has_total_deadline_and_safe_timeout(monkeypatch):
    from unittest.mock import AsyncMock
    from tasteduel.api import body_limit

    original_timeout = asyncio.timeout
    monkeypatch.setattr(body_limit.asyncio, "timeout", lambda _: original_timeout(0.01))
    sent = []

    async def receive():
        await asyncio.sleep(1)

    async def send(message):
        sent.append(message)

    await body_limit.BoundedBodyMiddleware(AsyncMock())({"type": "http", "method": "POST"}, receive, send)
    assert sent[0]["status"] == 408
    assert b'"REQUEST_TIMEOUT"' in sent[1]["body"]


@pytest.mark.parametrize("state", ["expired", "revoked"])
def test_stale_cookie_can_renew_guest_without_restoring_old_access(
    api_client, db_engine, expired_guest_cookie, state
):
    assert api_client.post("/v1/sessions", json={}).status_code == 201
    old_token = api_client.cookies.get("tasteduel_session")
    owner = UUID(old_token.split(".", 1)[0])
    if state == "expired":
        old_token = expired_guest_cookie
        api_client.cookies.set("tasteduel_session", old_token, domain="testserver.local", path="/")
    else:
        with scoped_session(db_engine, owner) as db:
            row = db.get(m.Session, owner)
            row.revoked_at = datetime.now(UTC)
    assert api_client.get("/v1/sessions/current").status_code == 401
    result = api_client.post("/v1/sessions", json={})
    assert result.status_code == 201
    assert api_client.cookies.get("tasteduel_session") != old_token
    assert result.json()["resumable_game_ids"] == []


def test_lost_clear_response_retry_with_revoked_cookie_remains_idempotent(api_client):
    assert api_client.post("/v1/sessions", json={}).status_code == 201
    old_token = api_client.cookies.get("tasteduel_session")
    assert api_client.delete("/v1/sessions/current").status_code == 204
    retry = api_client.delete("/v1/sessions/current", headers={"Cookie": f"tasteduel_session={old_token}"})
    assert retry.status_code == 204
    assert "Max-Age=0" in retry.headers["set-cookie"]


def test_throttled_guest_can_always_revoke_its_session(db_engine):
    app = create_app(
        Settings(cookie_secure=True, allowed_origins=("https://testserver",), guest_mutations_per_minute=1),
        engine=db_engine,
    )
    with TestClient(app, base_url="https://testserver", headers={"Origin": "https://testserver"}) as client:
        assert client.post("/v1/sessions", json={}).status_code == 201
        old_token = client.cookies.get("tasteduel_session")
        assert client.post("/v1/sessions", json={}).status_code == 200
        assert client.post("/v1/sessions", json={}).status_code == 429
        assert client.delete("/v1/sessions/current").status_code == 204
        assert (
            client.get(
                "/v1/sessions/current", headers={"Cookie": f"tasteduel_session={old_token}"}
            ).status_code
            == 401
        )
