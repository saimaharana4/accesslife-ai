"""Actual curator -> SQL bridge with synthetic provider/model contracts only.

The mock normalized Qloo envelope exercises production provenance branches; no
network call or live-agent readiness claim is made by this test.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from tasteduel.agents.round_curator import RoundCuratorAgent
from tasteduel.persistence import models as m
from tasteduel.persistence.db import scoped_session
from tasteduel.ports.curator import ModelUnavailable

from curator.synthetic import ScriptedModel, call, finish, provider


def test_insufficient_coverage_returns_actionable_safe_error_and_no_playable_round(gameplay, owned_seed):
    port, upstream, _ = provider(counts=(8,))
    model = ScriptedModel(call("fetch_ranked", target_domain="movie", limit=10),
        call("stop", reason="insufficient_coverage"))
    curator = RoundCuratorAgent(provider=port, model=model, capabilities={"artist": ("movie",)})
    client, owner, _ = gameplay(generator=curator)
    response = client.post('/v1/games', json=owned_seed(owner),
        headers={'Idempotency-Key':'synthetic-insufficient-coverage'})
    assert response.status_code == 422
    error = response.json()['error']
    assert error['code'] == 'GENERATION_INSUFFICIENT_COVERAGE'
    assert error['retryable'] is False
    assert 'choice' not in response.text and 'snapshot' not in response.text
    assert len(upstream.requests) == 1


@pytest.mark.parametrize("fallback", [False, True])
def test_real_curator_code_preserves_full_synthetic_execution_receipt(gameplay, db_engine, fallback):
    port, upstream, admission = provider()
    model = (
        ScriptedModel(ModelUnavailable("SYNTHETIC_MODEL_UNAVAILABLE"))
        if fallback
        else ScriptedModel(call("fetch_ranked", target_domain="movie", limit=20), finish)
    )
    curator = RoundCuratorAgent(provider=port, model=model, capabilities={"artist": ("movie",)})
    client, owner, _ = gameplay(generator=curator)
    internal, external = uuid4(), uuid4()
    with scoped_session(db_engine, owner) as db:
        db.add(
            m.Entity(
                id=internal,
                session_id=owner,
                provider="qloo",
                provider_entity_id=str(external),
                entity_type="artist",
                name="SYNTHETIC bridge seed",
                attribution="Synthetic provider contract",
                rights_policy="synthetic_contract",
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
    body = {"seed_entity_id": str(internal), "seed_type": "artist"}
    headers = {"Idempotency-Key": "synthetic-curator-bridge-key"}
    created = client.post("/v1/games", json=body, headers=headers)
    assert created.status_code == 201
    game = created.json()
    assert game["seed"]["id"] == str(internal) and str(external) not in created.text
    assert game["curator_mode"] == ("deterministic_qloo" if fallback else "genuine_agent")
    assert "curation_summary" not in game["current_round"]
    with scoped_session(db_engine, owner) as db:
        row = db.scalar(select(m.CurationReceipt).where(m.CurationReceipt.game_id == UUID(game["game_id"])))
        saved = row.full_receipt
        assert row.seed_entity_id == internal
        assert saved["seed_entity_id"] == str(external)
        assert saved["qloo_request_count"] == saved["qloo_reserved_count"] == 1
        assert saved["five_round_path_verified"] and saved["final_pool_status"] == "ready"
        assert saved["policy_configuration"]["near_tie_ratio"] == 0.05
        assert saved["policy_configuration"]["rounds"] == 5
        assert len(saved["evaluation_feedback"]) == 1 and saved["action_trace"]
        assert row.model_request_count == (1 if fallback else 2)
        assert row.curator_mode == game["curator_mode"]
        assert saved["model_usage_complete"] is (not fallback)
    retry = client.post("/v1/games", json=body, headers=headers)
    assert retry.status_code == 200 and retry.json() == game
    assert len(upstream.requests) == admission.admitted == 1
    assert len(model.observed) == (1 if fallback else 2)
