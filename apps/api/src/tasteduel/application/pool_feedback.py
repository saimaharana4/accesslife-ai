"""Bounded private tool feedback, explicitly separate from browser curation DTOs."""

from typing import Annotated, Literal
import re

from pydantic import Field, StrictBool, StrictInt

from tasteduel.domain.duel_pool import PoolBuildResult
from tasteduel.domain.types import StrictRecord

Counter = Annotated[StrictInt, Field(ge=0, le=1000)]
Reason = Literal[
    "invalid_identity",
    "duplicate_identity",
    "seed_self_match",
    "missing_metadata",
    "ambiguous_name",
    "ambiguous_identity",
    "domain_mismatch",
    "context_mismatch",
    "missing_or_nonfinite_score",
    "invalid_position",
    "duplicate_position",
    "invalid_category_metadata",
    "ordering_unverified",
    "unsupported_domain",
    "invalid_seed_identity",
    "missing_context",
    "missing_provenance",
    "candidate_limit_exceeded",
    "contradictory_order",
    "tied_score",
    "near_tie",
    "fewer_than_ten_eligible_candidates",
    "diversity_unmet",
    "no_complete_no_repeat_path",
    "search_budget_exhausted",
    "diversity_optimization_budget_exhausted",
    "provider_error",
    "provider_needs_input",
    "provider_empty",
    "provider_contract_invalid",
    "unsupported_provenance",
    "invalid_evidence_time",
    "evidence_expired",
    "unrecognized_validation_reason",
]
Correction = Literal[
    "confirm_seed_selection",
    "provider_capability_gate_required",
    "request_more_candidates_within_limit",
    "try_another_supported_target_or_seed",
    "supported_category_metadata_required",
    "retry_bounded_evaluation",
    "none",
]
_REASONS = frozenset(Reason.__args__)


class ReasonCount(StrictRecord):
    reason: Reason
    count: Counter


class CuratorPoolFeedback(StrictRecord):
    """No entity titles, IDs, pair lists, winners, score values or freeform text."""

    status: Literal[
        "ready",
        "insufficient_coverage",
        "invalid_snapshot",
        "evaluation_limited",
        "provider_unavailable",
        "needs_input",
    ]
    policy_version: Literal["duel-pool-v1"] = "duel-pool-v1"
    policy_fingerprint: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    target_domain: Literal["artist", "movie"] | None = None
    context_hash: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")] | None = None
    counts_scope: Literal["normalized_snapshot"] = "normalized_snapshot"
    candidates_received: Counter = 0
    candidates_accepted: Counter = 0
    candidates_rejected: Counter = 0
    candidate_reason_incidences: Annotated[tuple[ReasonCount, ...], Field(max_length=20)] = ()
    pair_exclusions: Annotated[tuple[ReasonCount, ...], Field(max_length=4)] = ()
    eligible_pair_count: Counter = 0
    pool_pair_count: Annotated[StrictInt, Field(ge=0, le=15)] = 0
    category_metadata_available: StrictBool = False
    categories_available: Counter = 0
    candidates_without_categories: Counter = 0
    categories_required: Annotated[StrictInt, Field(ge=0, le=10)] = 0
    categories_in_witness_path: Counter = 0
    bands_required: Annotated[StrictInt, Field(ge=1, le=3)] = 1
    bands_in_witness_path: Annotated[tuple[Literal["easy", "medium", "hard"], ...], Field(max_length=3)] = ()
    five_round_path_verified: StrictBool = False
    diversity_requirements_satisfied: StrictBool = False
    search_limit_exceeded: StrictBool = False
    objective_limited: StrictBool = False
    reasons: Annotated[tuple[Reason, ...], Field(max_length=20)] = ()
    corrections: Annotated[tuple[Correction, ...], Field(max_length=6)] = ()
    semantics: Literal["engineering_heuristics_not_human_difficulty_or_surprise"] = (
        "engineering_heuristics_not_human_difficulty_or_surprise"
    )


def feedback_from_pool(result: PoolBuildResult) -> CuratorPoolFeedback:
    value = result.evaluation

    def reason(code):
        return code if code in _REASONS else "unrecognized_validation_reason"

    reasons = tuple(dict.fromkeys(reason(code) for code in value.correction_reasons))
    corrections = []
    if value.search_limit_exceeded:
        corrections.append("retry_bounded_evaluation")
    if "ordering_unverified" in reasons or "missing_provenance" in reasons:
        corrections.append("provider_capability_gate_required")
    if value.categories_required > value.categories_available or any(
        code == "invalid_category_metadata" for code, _ in value.candidate_rejections
    ):
        corrections.append("supported_category_metadata_required")
    if not value.complete_path and value.candidates_received < 20:
        corrections.append("request_more_candidates_within_limit")
    if not value.complete_path:
        corrections.append("try_another_supported_target_or_seed")
    return CuratorPoolFeedback(
        status=result.status,
        policy_version=value.policy_version,
        policy_fingerprint=value.policy_fingerprint,
        target_domain=value.domain if value.domain in ("artist", "movie") else None,
        context_hash=value.context_hash if re.fullmatch(r"[a-f0-9]{64}", value.context_hash or "") else None,
        candidates_received=value.candidates_received,
        candidates_accepted=value.candidates_accepted,
        candidates_rejected=value.candidates_rejected,
        candidate_reason_incidences=tuple(
            ReasonCount(reason=reason(code), count=count) for code, count in value.candidate_rejections
        ),
        pair_exclusions=tuple(
            ReasonCount(reason=reason(code), count=count) for code, count in value.pair_rejections
        ),
        eligible_pair_count=value.eligible_pair_count,
        pool_pair_count=value.pair_count,
        category_metadata_available=value.categories_available > 0,
        categories_available=value.categories_available,
        candidates_without_categories=value.candidates_without_categories,
        categories_required=value.categories_required,
        categories_in_witness_path=value.categories_in_path,
        bands_required=value.bands_required,
        bands_in_witness_path=value.bands_in_path,
        five_round_path_verified=value.complete_path,
        diversity_requirements_satisfied=value.diversity_satisfied,
        search_limit_exceeded=value.search_limit_exceeded,
        objective_limited=value.objective_limited,
        reasons=reasons,
        corrections=tuple(dict.fromkeys(corrections)) or ("none",),
    )
