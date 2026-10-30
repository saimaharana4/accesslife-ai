from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from tasteduel.api.main import create_app
from tasteduel.config import Settings
from tasteduel.persistence import models as m
from tasteduel.persistence.db import scoped_session
from tasteduel.ports.qloo import EntityMetadata, ProviderFailure, QlooResult, ResolutionIssue


class SyntheticSearchPort:
    """Normalized synthetic contracts, never a live coverage claim."""

    def __init__(self, result):
        self.result = result
        self.calls = []

    @asynccontextmanager
    async def request_budget(self, **kwargs):
        assert kwargs == {"max_requests": 2, "deadline_seconds": 8}
        yield None

    async def resolve_seed(self, request):
        self.calls.append(request)
        return self.result


@pytest.fixture
def search_client(db_engine):
    clients = []

    def make(result):
        port = SyntheticSearchPort(result)

        class Runtime:
            async def close(self):
                pass

        runtime = Runtime()
        runtime.port = port

        async def factory(*_):
            return runtime

        app = create_app(
            Settings(qloo_enabled=True, allowed_origins=("https://testserver",)),
            engine=db_engine,
            qloo_factory=factory,
        )
        client = TestClient(app, base_url="https://testserver", headers={"Origin": "https://testserver"})
        client.__enter__()
        clients.append(client)
        assert client.post("/v1/sessions", json={}).status_code == 201
        return client, port

    yield make
    for client in reversed(clients):
        client.__exit__(None, None, None)


def test_search_reuses_owned_metadata_but_never_exposes_provider_identity(search_client, db_engine):
    external = uuid4()
    client, port = search_client(
        QlooResult("ok", entities=(EntityMetadata(external, "SYNTHETIC artist", "artist"),))
    )
    responses = [
        client.get("/v1/entities/search", params={"q": "SYNTHETIC", "type": "artist"}) for _ in range(2)
    ]
    assert all(response.status_code == 200 for response in responses)
    assert responses[0].json() == responses[1].json()
    public = responses[0].json()["results"][0]
    assert public["id"] != str(external)
    assert str(external) not in responses[0].text
    assert len(port.calls) == 2
    owner = UUID(client.cookies.get("tasteduel_session").split(".")[0])
    with scoped_session(db_engine, owner) as db:
        row = db.scalar(select(m.Entity).where(m.Entity.session_id == owner))
        assert row.id == UUID(public["id"]) and row.provider_entity_id == str(external)


def test_same_upstream_search_identity_is_isolated_per_guest(search_client):
    result = QlooResult("ok", entities=(EntityMetadata(uuid4(), "SYNTHETIC movie", "movie"),))
    first, _ = search_client(result)
    second, _ = search_client(result)
    payloads = [
        client.get("/v1/entities/search", params={"q": "SYNTHETIC", "type": "movie"}).json()
        for client in (first, second)
    ]
    assert payloads[0]["results"][0]["id"] != payloads[1]["results"][0]["id"]


def test_search_ambiguity_remains_explicit_and_never_starts_generation(search_client):
    result = QlooResult(
        "needs_input",
        issues=(
            ResolutionIssue(
                "ambiguous",
                tuple(EntityMetadata(uuid4(), f"SYNTHETIC artist {i}", "artist") for i in range(2)),
            ),
        ),
    )
    client, _ = search_client(result)
    response = client.get("/v1/entities/search", params={"q": "SYNTHETIC", "type": "artist"})
    assert response.json()["status"] == "needs_input" and len(response.json()["results"]) == 2
    assert client.get("/v1/sessions/current").json()["resumable_game_ids"] == []


def test_search_provider_errors_are_sanitized_without_fallback(search_client):
    client, port = search_client(QlooResult("error", error=ProviderFailure("PRIVATE_MARKER_AUTH")))
    response = client.get("/v1/entities/search", params={"q": "SYNTHETIC", "type": "artist"})
    assert response.status_code == 503 and response.json()["error"]["code"] == "QLOO_UNAVAILABLE"
    assert "PRIVATE_MARKER" not in response.text and len(port.calls) == 1
