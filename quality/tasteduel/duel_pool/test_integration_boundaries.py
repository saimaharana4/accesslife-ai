"""Pure bridge/time/feedback regressions; all provider values are manufactured."""

from dataclasses import replace
from datetime import timedelta

import pytest

from tasteduel.application.pool_feedback import feedback_from_pool
from tasteduel.application.pool_preparation import prepare_qloo_pool
from tasteduel.domain.duel_pool import build_pool
from tasteduel.domain.duel_pool import builder
from tasteduel.ports.qloo import QlooResult
from tasteduel.adapters.qloo.adapter import QlooMcpAdapter
from tasteduel.ports.qloo import ranked_context_hash
from quality.tasteduel.qloo.samples import envelope

from quality.tasteduel.duel_pool_review.test_projection_and_bridge import (
    NOW,
    REQUEST,
    CONFIRMED_SEED,
    prepare,
    synthetic_verified_result,
)
from .synthetic import Category, snapshot


async def test_typed_context_helper_matches_actual_provider_adapter_request_fingerprint():
    class OfflineChild:
        async def call_tool(self, name, arguments):
            assert name == "qloo_recommend"
            assert arguments["signals"] == [str(REQUEST.seed_id)]
            return {"structuredContent": envelope(), "_tasteduel_http_statuses": ()}

    result = await QlooMcpAdapter(OfflineChild()).ranked_candidates(REQUEST)
    assert result.evidence.context_hash == ranked_context_hash(REQUEST)
    assert result.evidence.ordering_verified is False


def test_private_feedback_and_pool_types_are_not_added_to_browser_openapi():
    from tasteduel.api.main import create_app
    from tasteduel.config import Settings

    schema = create_app(Settings(qloo_enabled=False)).openapi()
    names = schema["components"]["schemas"]
    assert not {"CuratorPoolFeedback", "RankingSnapshot", "PoolBuildResult", "PrivatePair"}.intersection(
        names
    )
    assert "band" not in names["PlayableRoundPublic"]["properties"]


@pytest.mark.parametrize("position", [True, False, -1, None, "1", 1.5])
def test_bridge_rejects_invalid_provider_positions_before_conversion(position):
    result = synthetic_verified_result()
    changed = replace(result.candidates[0], position=position)
    prepared = prepare(replace(result, candidates=(changed,) + result.candidates[1:]))
    assert prepared.pool is None
    assert prepared.feedback.reasons == ("provider_contract_invalid",)


@pytest.mark.parametrize(
    "status,expected",
    [("error", "provider_unavailable"), ("needs_input", "needs_input"), ("empty", "insufficient_coverage")],
)
def test_terminal_provider_status_never_becomes_a_fixture_pool(status, expected):
    value = prepare(QlooResult(status))
    assert value.pool is None
    assert value.feedback.status == expected
    assert not value.feedback.five_round_path_verified


@pytest.mark.parametrize(
    "offset,expiry,reason",
    [
        (1, 2, "invalid_evidence_time"),
        (-2, 2, "evidence_expired"),
        (-1, -0.5, "evidence_expired"),
        (0, 25, "invalid_evidence_time"),
    ],
)
def test_explicit_cache_and_evidence_times_cannot_be_faked_fresh(offset, expiry, reason):
    result = synthetic_verified_result()
    result = replace(result, evidence=replace(result.evidence, observed_at=NOW + timedelta(hours=offset)))
    prepared = prepare_qloo_pool(
        result,
        REQUEST,
        rng_seed="synthetic",
        now=NOW,
        evidence_expires_at=NOW + timedelta(hours=expiry),
        confirmed_seed=CONFIRMED_SEED,
    )
    assert prepared.pool is None and prepared.feedback.reasons == (reason,)


def test_naive_timestamps_are_rejected():
    result = synthetic_verified_result()
    prepared = prepare_qloo_pool(
        result,
        REQUEST,
        rng_seed="synthetic",
        now=NOW.replace(tzinfo=None),
        evidence_expires_at=NOW + timedelta(hours=1),
        confirmed_seed=CONFIRMED_SEED,
    )
    assert prepared.feedback.reasons == ("invalid_evidence_time",)


def test_seed_domain_cannot_be_relabelled_to_claim_a_cross_domain_round():
    prepared = prepare(synthetic_verified_result(), replace(REQUEST, seed_domain="movie"))
    assert prepared.pool is None and prepared.feedback.reasons == ("context_mismatch",)


def test_selected_seed_identity_must_match_confirmed_provider_metadata():
    prepared = prepare_qloo_pool(
        synthetic_verified_result(),
        REQUEST,
        rng_seed="synthetic",
        now=NOW,
        evidence_expires_at=NOW + timedelta(hours=1),
        confirmed_seed=replace(CONFIRMED_SEED, id=REQUEST.seed_id.__class__(int=999)),
    )
    assert prepared.pool is None and prepared.feedback.reasons == ("context_mismatch",)


def test_category_rejection_is_actionable_and_reason_incidences_are_not_entity_counts():
    value = snapshot()
    changed = replace(value.candidates[0], categories=(Category("", "synthetic"),), ambiguous=True)
    pool = build_pool(replace(value, candidates=(changed,) + value.candidates[1:]), rng_seed="synthetic")
    feedback = feedback_from_pool(pool)
    assert feedback.candidates_rejected == 1
    incidences = {count.reason: count.count for count in feedback.candidate_reason_incidences}
    assert incidences["invalid_category_metadata"] == incidences["ambiguous_identity"] == 1
    assert "supported_category_metadata_required" in feedback.corrections
    assert "unrecognized_validation_reason" not in incidences


def test_search_budget_exhaustion_is_not_claimed_as_proven_insufficiency(monkeypatch):
    monkeypatch.setattr(builder, "MAX_SEARCH_STATES", 0)
    result = build_pool(snapshot(), rng_seed="synthetic-budget")
    assert result.status == "evaluation_limited"
    assert not result.path and not result.evaluation.complete_path
    assert result.evaluation.search_limit_exceeded
    assert "no_complete_no_repeat_path" not in result.evaluation.correction_reasons


def test_objective_budget_can_stop_without_discarding_a_proven_valid_path(monkeypatch):
    real = builder.find_path
    calls = 0

    def budgeted(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise builder.SearchBudgetExceeded()
        return real(*args, **kwargs)

    rows = tuple(
        replace(row, affinity=1.0 if index < 5 else 0.0, categories=())
        for index, row in enumerate(snapshot(10).candidates)
    )
    monkeypatch.setattr(builder, "find_path", budgeted)
    result = build_pool(snapshot(candidates=rows), rng_seed="synthetic-objective")
    assert result.status == "ready" and len(result.path) == 5
    assert result.evaluation.objective_limited
    assert "diversity_optimization_budget_exhausted" in result.evaluation.correction_reasons
