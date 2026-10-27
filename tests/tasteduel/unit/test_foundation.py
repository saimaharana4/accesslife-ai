"""Foundation contracts and boundaries; no AccessLife fixtures or provider calls."""

import json
import math
from pathlib import Path
import sys
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from tasteduel.api.main import create_app
from tasteduel.config import Settings, validate_local_url
from tasteduel.domain.idempotency import request_signature


def test_export_is_actual_application_paths_and_no_private_receipt_schema():
    schema = create_app(Settings()).openapi()
    required = {
        "/v1/sessions",
        "/v1/sessions/current",
        "/v1/entities/search",
        "/v1/games",
        "/v1/games/{game_id}",
        "/v1/games/{game_id}/generation",
        "/v1/games/{game_id}/round",
        "/v1/games/{game_id}/answer",
        "/v1/games/{game_id}/advance",
        "/v1/games/{game_id}/results",
        "/v1/discoveries",
        "/v1/discoveries/{entity_id}",
        "/v1/challenges",
        "/v1/challenges/{slug}",
        "/v1/challenges/{slug}/plays",
        "/v1/health/live",
        "/v1/health/ready",
    }
    assert set(schema["paths"]) == required
    assert "CurationReceipt" not in schema["components"]["schemas"]
    assert "MutationReceipt" not in schema["components"]["schemas"]
    public = schema["components"]["schemas"]["PlayableRoundPublic"]
    assert public["additionalProperties"] is False
    assert not {"winning_choice_id", "rank", "affinity", "evidence", "curation_summary"}.intersection(
        public["properties"]
    )
    assert any(server["url"] == "/api" for server in schema["servers"])


def test_committed_contract_export_has_no_drift():
    actual = create_app(Settings()).openapi()
    path = Path(__file__).resolve().parents[3] / "packages/contracts/openapi.json"
    assert json.loads(path.read_text(encoding="utf-8")) == actual


def test_signature_is_canonical_and_scoped_to_owner_operation_and_typed_body():
    owner = uuid4()
    first = request_signature(owner, "answer", {"b": 2, "a": 1})
    assert first == request_signature(owner, "answer", {"a": 1, "b": 2})
    assert len(first) == 64
    assert first != request_signature(owner, "advance", {"a": 1, "b": 2})
    assert first != request_signature(uuid4(), "answer", {"a": 1, "b": 2})
    assert first != request_signature(owner, "answer", {"a": 2, "b": 2})
    with pytest.raises(ValueError):
        request_signature(owner, "answer", {"a": math.nan})


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://tasteduel_runtime:synthetic@cloud.example.invalid:55435/tasteduel_prompt5",
        "postgresql+psycopg://accesslife:synthetic@127.0.0.1:5432/accesslife",
        "postgresql+psycopg://tasteduel_migrator:synthetic@127.0.0.1:55435/tasteduel_prompt5",
        "sqlite:///tasteduel_prompt5.db",
    ],
)
def test_runtime_rejects_remote_legacy_wrong_role_or_wrong_driver(url):
    with pytest.raises(ValueError, match="dedicated local"):
        validate_local_url(url)


def test_compose_database_allowlist_is_explicit_and_non_external(monkeypatch):
    url = "postgresql+psycopg://tasteduel_runtime:synthetic@database:5432/tasteduel_prompt5"
    monkeypatch.delenv("TASTEDUEL_CONTAINER_MODE", raising=False)
    with pytest.raises(ValueError, match="dedicated local"):
        validate_local_url(url)
    monkeypatch.setenv("TASTEDUEL_CONTAINER_MODE", "true")
    assert validate_local_url(url) == url
    assert validate_local_url(
        "postgresql+psycopg://tasteduel_migrator:synthetic@127.0.0.1:55436/tasteduel_prompt5",
        migration=True,
    ).endswith("/tasteduel_prompt5")
    for unsafe in (
        "postgresql+psycopg://tasteduel_runtime:synthetic@db:5432/tasteduel_prompt5",
        "postgresql+psycopg://tasteduel_runtime:synthetic@database:5433/tasteduel_prompt5",
        "postgresql+psycopg://tasteduel_runtime:synthetic@database:5432/accesslife",
        "postgresql+psycopg://tasteduel_runtime:synthetic@cloud.example.invalid:5432/tasteduel_prompt5",
    ):
        with pytest.raises(ValueError, match="dedicated local"):
            validate_local_url(unsafe)


def test_no_config_does_not_import_legacy_or_contact_database():
    app = create_app(Settings(database_url=None))
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.get("/v1/health/live").json()["generation_available"] is False
        assert client.get("/v1/health/ready").status_code == 503
    assert "accesslife.api.main" not in sys.modules


def test_unknown_seed_cannot_create_a_game_and_cookies_are_private(create_guest):
    client, _ = create_guest()
    response = client.post("/v1/sessions", json={})
    assert response.status_code == 200
    assert set(response.json()) == {"active", "expires_at", "resumable_game_ids"}
    assert "token" not in response.text
    assert "token_hash" not in response.text
    response = client.post(
        "/v1/games",
        json={"seed_entity_id": str(uuid4()), "seed_type": "artist", "mode": "solo"},
        headers={"Idempotency-Key": "synthetic-foundation-create"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert client.get("/v1/sessions/current").json()["resumable_game_ids"] == []


def test_local_readiness_reports_database_not_generation(api_client):
    response = api_client.get("/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "component": "api", "generation_available": False}
