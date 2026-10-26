"""Private execution facts and deterministic authority, without network/model calls."""

import json
import time

import tasteduel.agents.round_curator as curator_module
from tasteduel.agents.round_curator import CuratorLimits, RoundCuratorAgent
from tasteduel.domain.types import CuratorMode
from tasteduel.ports.curator import ModelUnavailable

from curator.synthetic import GAME_ID, SEED, ScriptedModel, call, finish, provider


def build_agent(model, **provider_options):
    guarded, inner, admission = provider(**provider_options)
    agent = RoundCuratorAgent(
        provider=guarded,
        model=model,
        capabilities={"artist": ("movie", "artist")},
    )
    return agent, inner, admission


async def run(agent):
    return await agent.curate(SEED, game_id=GAME_ID, rng_seed="review-private-synthetic-rng")


async def test_agent_selects_context_but_cannot_change_snapshot_winners():
    """Selecting another permitted domain changes the strategy, never score authority."""
    for domain in ("movie", "artist"):
        model = ScriptedModel(call("fetch_ranked", target_domain=domain, limit=20), finish)
        agent, inner, _ = build_agent(model)
        result = await run(agent)
        assert result.pool.status == "ready"
        assert inner.requests[0].target_domain == domain
        assert all(pair.first.domain == pair.second.domain == domain for pair in result.pool.pairs)
        for pair in result.pool.pairs:
            expected = max((pair.first, pair.second), key=lambda candidate: candidate.affinity).id
            assert pair.winner_id == expected
        assert (
            len({choice.entity.id for pair in result.pool.path for choice in (pair.left, pair.right)}) == 10
        )


async def test_model_and_receipt_never_receive_private_candidate_ids_scores_or_future_pairs():
    model = ScriptedModel(call("fetch_ranked", target_domain="movie", limit=20), finish)
    agent, _, _ = build_agent(model)
    result = await run(agent)
    transcript = json.dumps(model.observed)
    receipt = result.receipt.model_dump_json()
    trace = str(result.trace)
    for pair in result.pool.pairs:
        for entity in (pair.first, pair.second):
            for private in (str(entity.id), entity.name):
                assert private not in transcript
                assert private not in receipt
                assert private not in trace
        assert str(pair.id) not in receipt
        assert str(pair.id) not in trace
    for forbidden in ("winner_id", "winner_side", "affinity", "relative_gap", "chain_of_thought"):
        assert forbidden not in receipt
        assert forbidden not in trace


async def test_model_unavailable_fallback_keeps_actual_attempt_count_and_label():
    marker = "PRIVATE_SYNTHETIC_SDK_EXCEPTION_NOT_FOR_TRACE"
    model = ScriptedModel(ModelUnavailable(marker))
    agent, inner, admission = build_agent(model)
    result = await run(agent)
    assert result.pool is not None and result.pool.status == "ready"
    assert result.receipt.curator_mode == CuratorMode.DETERMINISTIC_QLOO
    assert result.receipt.model_request_count == len(model.observed) == 1
    assert result.receipt.model_version == model.model_version
    assert result.receipt.qloo_request_count == admission.admitted == len(inner.dispatched)
    assert result.receipt.five_round_path_verified
    assert marker not in result.receipt.model_dump_json()
    assert marker not in str(result.trace)


async def test_model_loss_after_valid_feedback_reuses_evidence_without_extra_provider_work():
    model = ScriptedModel(
        call("fetch_ranked", target_domain="movie", limit=20),
        ModelUnavailable("PRIVATE_SYNTHETIC_EXCEPTION"),
    )
    agent, inner, _ = build_agent(model)
    result = await run(agent)
    assert result.pool is not None and result.pool.status == "ready"
    assert len(inner.requests) == 1
    assert result.receipt.curator_mode == CuratorMode.DETERMINISTIC_QLOO
    assert result.receipt.model_request_count == len(model.observed) == 2
    assert result.receipt.bounded_correction_count == 0


async def test_fallback_remains_subject_to_qloo_validator_veto():
    model = ScriptedModel(ModelUnavailable())
    agent, inner, _ = build_agent(model, counts=(4, 4))
    result = await run(agent)
    assert result.pool is None or result.pool.status != "ready"
    assert not result.receipt.five_round_path_verified
    assert result.receipt.curator_mode == CuratorMode.DETERMINISTIC_QLOO
    assert result.receipt.model_request_count == 1
    assert len(inner.requests) <= 2


async def test_unfinished_ready_candidate_pool_is_not_a_publishable_outcome():
    guarded, _, _ = provider()
    agent = RoundCuratorAgent(
        provider=guarded,
        model=ScriptedModel(call("fetch_ranked", target_domain="movie", limit=20)),
        capabilities={"artist": ("movie",)},
        limits=CuratorLimits(max_model_requests=1),
    )
    result = await run(agent)
    assert result.failure_code == "MODEL_REQUEST_BUDGET"
    assert result.pool is None
    assert not result.receipt.five_round_path_verified


async def test_cpu_validation_cannot_publish_success_after_absolute_deadline(monkeypatch):
    original = curator_module.prepare_qloo_pool

    def delayed_validation(*args, **kwargs):
        # CPU work does not yield to an asyncio timeout; the curator must recheck time.
        time.sleep(0.03)
        return original(*args, **kwargs)

    monkeypatch.setattr(curator_module, "prepare_qloo_pool", delayed_validation)
    guarded, _, _ = provider()
    agent = RoundCuratorAgent(
        provider=guarded,
        model=ScriptedModel(call("fetch_ranked", target_domain="movie", limit=20), finish),
        capabilities={"artist": ("movie",)},
        limits=CuratorLimits(overall_seconds=0.02),
    )
    result = await run(agent)
    assert result.pool is None
    assert result.failure_code == "CURATION_DEADLINE"
    assert not result.receipt.five_round_path_verified
