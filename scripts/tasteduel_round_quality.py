"""Aggregate-only local quality inspection; never publish provider contestants or scores."""

from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/api/src"))

from tasteduel.application.pool_preparation import PreparedPool  # noqa: E402
from tasteduel.domain.duel_pool.validation import canonical_name  # noqa: E402
from tasteduel.ports.qloo import QlooResult  # noqa: E402


def audit_prepared_pool(result: QlooResult, prepared: PreparedPool) -> dict[str, object]:
    """Inspect privately in memory; return only a deliberately fixed aggregate allowlist.

    This tests technical feasibility, never human surprise, preference or difficulty.
    A witness path proves one valid five-round continuation, not every adaptive path.
    """
    rows = result.candidates
    names = Counter(canonical_name(row.entity.name) for row in rows)
    identities = Counter(row.entity.id for row in rows)
    pool, snapshot = prepared.pool, prepared.snapshot
    path = pool.path if pool else ()
    entities = [choice.entity for pair in path for choice in (pair.left, pair.right)]
    sides = Counter(pair.winner_side for pair in path)
    feedback = prepared.feedback
    pair_by_id = {pair.id: pair for pair in pool.pairs} if pool else {}
    strict_winners = bool(path) and all(
        pair_by_id[shown.pair_id].winner_id
        == (shown.left.entity.id if shown.winner_side == "left" else shown.right.entity.id)
        and pair_by_id[shown.pair_id].first.affinity > pair_by_id[shown.pair_id].second.affinity
        for shown in path
    )
    return {
        "provider_status": result.status,
        "pool_status": pool.status if pool else feedback.status,
        "target_domain": snapshot.domain if snapshot else feedback.target_domain,
        "cross_domain": snapshot.seed_domain != snapshot.domain if snapshot else False,
        "candidates_received": len(rows),
        "candidates_accepted": pool.evaluation.candidates_accepted if pool else 0,
        "duplicate_identity_rows": sum(count for count in identities.values() if count > 1),
        "duplicate_normalized_name_rows": sum(count for count in names.values() if count > 1),
        "image_metadata_count": sum(bool(row.entity.image_url) for row in rows),
        "image_rights_verified_count": sum(row.entity.image_rights_verified is True for row in rows),
        "path_owned_fallback_count": sum(
            choice.artwork_mode == "owned_fallback" for pair in path for choice in (pair.left, pair.right)
        ),
        "candidate_rejections": dict(pool.evaluation.candidate_rejections) if pool else {},
        "pair_rejections": dict(pool.evaluation.pair_rejections) if pool else {},
        "eligible_pair_count": pool.evaluation.eligible_pair_count if pool else 0,
        "retained_pair_count": len(pool.pairs) if pool else 0,
        "path_round_count": len(path),
        "path_distinct_contestants": len({row.id for row in entities}),
        "path_no_repeat": len(path) == 5 and len({row.id for row in entities}) == 10,
        "path_same_type": bool(path) and all(
            shown.left.entity.domain == shown.right.entity.domain == snapshot.domain for shown in path
        ),
        "ordering_verified": bool(snapshot and snapshot.ordering_verified),
        "path_strict_verified_winners": strict_winners,
        "path_sides_balanced": len(path) == 5 and abs(sides["left"] - sides["right"]) == 1,
        "path_band_counts": dict(Counter(pair_by_id[shown.pair_id].band for shown in path)),
        "pool_band_counts": dict(Counter(pair.band for pair in pool.pairs)) if pool else {},
        "categories_available": pool.evaluation.categories_available if pool else 0,
        "candidates_without_categories": pool.evaluation.candidates_without_categories if pool else len(rows),
        "policy_version": pool.policy.version if pool else None,
        "policy_fingerprint": pool.policy.fingerprint if pool else feedback.policy_fingerprint,
        "human_surprise_calibrated": False,
        "human_difficulty_calibrated": False,
        "explanation_policy": "factual_request_specific_rank_only",
    }
