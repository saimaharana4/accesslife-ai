"""Normalize typed port values into private frozen game evidence, with no I/O."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from tasteduel.application.pool_feedback import CuratorPoolFeedback, feedback_from_pool
from tasteduel.domain.duel_pool import (
    Candidate,
    PairQualityPolicy,
    PoolBuildResult,
    RankingSnapshot,
    build_pool,
)
from tasteduel.ports.qloo import EntityMetadata, QlooResult, RankedCandidatesRequest, ranked_context_hash


@dataclass(frozen=True)
class PreparedPool:
    feedback: CuratorPoolFeedback
    pool: PoolBuildResult | None = None
    snapshot: RankingSnapshot | None = None
    observed_at: datetime | None = None
    evidence_expires_at: datetime | None = None


def prepare_qloo_pool(
    result: QlooResult,
    request: RankedCandidatesRequest,
    *,
    rng_seed: str | int,
    now: datetime,
    evidence_expires_at: datetime,
    confirmed_seed: EntityMetadata,
    policy: PairQualityPolicy = PairQualityPolicy(),
) -> PreparedPool:
    """Only trusted provider orchestration can call this; no model-set ordering flag.

    TTLs enforce existing conservative product defaults, not contractual rights.
    Caller must also establish applicable retention permission before persistence.
    """
    request_valid = (
        isinstance(request.seed_id, UUID)
        and request.seed_domain in ("artist", "movie")
        and request.target_domain in ("artist", "movie")
        and type(request.limit) is int
        and 1 <= request.limit <= 20
    )
    transport = result.evidence.transport if result.evidence else "mcp"
    if transport not in ("mcp", "http_ranked"):
        request_valid = False
    context = ranked_context_hash(request, transport=transport) if request_valid else None

    def stop(reason, status="invalid_snapshot", corrections=("provider_capability_gate_required",)):
        return PreparedPool(
            CuratorPoolFeedback(
                status=status,
                policy_fingerprint=policy.fingerprint,
                target_domain=request.target_domain if request.target_domain in ("artist", "movie") else None,
                context_hash=context,
                candidates_received=len(result.candidates),
                reasons=(reason,),
                corrections=corrections,
                categories_required=policy.min_categories,
                bands_required=policy.min_bands,
            )
        )

    if not request_valid:
        return stop("provider_contract_invalid")
    if confirmed_seed.id != request.seed_id or confirmed_seed.domain != request.seed_domain:
        return stop("context_mismatch")
    if result.status == "needs_input" or result.issues:
        return stop("provider_needs_input", "needs_input", ("confirm_seed_selection",))
    if result.status == "error":
        return stop("provider_error", "provider_unavailable", ("try_another_supported_target_or_seed",))
    if result.status == "empty":
        return stop("provider_empty", "insufficient_coverage", ("try_another_supported_target_or_seed",))
    if result.status not in ("ok", "partial", "degraded") or len(result.candidates) > 20:
        return stop("provider_contract_invalid")
    evidence = result.evidence
    if evidence is None or evidence.ordering_verified is not True:
        return stop("ordering_unverified")
    if (
        evidence.provider != "qloo"
        or evidence.harness_version != "0.1.26"
        or evidence.score_field != "query.affinity"
    ):
        # The compact MCP score source/default ordering still lacks a live proof.
        return stop("unsupported_provenance")
    if evidence.context_hash != context:
        return stop("context_mismatch")
    times = (now, evidence.observed_at, evidence_expires_at)
    if any(
        not isinstance(time, datetime) or time.tzinfo is None or time.utcoffset() is None for time in times
    ):
        return stop("invalid_evidence_time")
    if (
        evidence.observed_at > now
        or evidence_expires_at <= evidence.observed_at
        or evidence_expires_at > evidence.observed_at + timedelta(hours=24)
    ):
        return stop("invalid_evidence_time")
    if now >= evidence_expires_at or now - evidence.observed_at > timedelta(hours=1):
        return stop("evidence_expired", corrections=("try_another_supported_target_or_seed",))
    if any(type(value.position) is not int or value.position < 0 for value in result.candidates):
        return stop("provider_contract_invalid")
    candidates = tuple(
        Candidate(
            id=value.entity.id,
            name=value.entity.name,
            domain=value.entity.domain,
            affinity=value.affinity,
            position=value.position + 1,
            context_hash=context,
            image_url=value.entity.image_url,
            image_rights_verified=value.entity.image_rights_verified,
            # No supported category metadata exists in the current port; never infer it.
        )
        for value in result.candidates
    )
    snapshot = RankingSnapshot(
        context,
        request.target_domain,
        request.seed_id,
        request.seed_domain,
        candidates,
        evidence.ordering_verified,
        evidence.provider,
        evidence.harness_version,
        evidence.score_field,
    )
    pool = build_pool(snapshot, rng_seed=rng_seed, policy=policy)
    return PreparedPool(feedback_from_pool(pool), pool, snapshot, evidence.observed_at, evidence_expires_at)
