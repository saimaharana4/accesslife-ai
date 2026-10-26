"""Offline aggregate-only engine demonstration using explicitly invented data."""

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/api/src"))

from tasteduel.application.pool_feedback import feedback_from_pool  # noqa: E402
from tasteduel.domain.duel_pool import (  # noqa: E402
    Candidate,
    Category,
    PairQualityPolicy,
    RankingSnapshot,
    build_pool,
)


def synthetic_report():
    context = hashlib.sha256(b"explicitly-synthetic-prompt7-context").hexdigest()
    rows = tuple(
        Candidate(
            UUID(int=index + 1),
            f"Invented fixture film {index}",
            "movie",
            float(100 - index),
            index + 1,
            context,
            categories=(Category(f"Fixture category {index % 4}", "synthetic"),),
        )
        for index in range(20)
    )
    snapshot = RankingSnapshot(
        context,
        "movie",
        UUID(int=1000),
        "artist",
        rows,
        True,
        provider="fixture",
        harness_version="synthetic-v1",
        score_field="fixture-score",
    )
    clustered = tuple(
        replace(row, affinity=(100 - index * 0.001) if index < 18 else 50.0 if index == 18 else 0.0)
        for index, row in enumerate(rows)
    )
    cases = (
        ("synthetic_broad_inventory", snapshot, PairQualityPolicy()),
        ("synthetic_tiny_inventory", replace(snapshot, candidates=rows[:8]), PairQualityPolicy()),
        (
            "synthetic_all_tied",
            replace(snapshot, candidates=tuple(replace(row, affinity=1.0) for row in rows)),
            PairQualityPolicy(),
        ),
        ("synthetic_near_tie_cluster", replace(snapshot, candidates=clustered), PairQualityPolicy()),
        (
            "synthetic_missing_required_categories",
            replace(snapshot, candidates=tuple(replace(row, categories=()) for row in rows)),
            PairQualityPolicy(min_categories=2),
        ),
    )
    return {
        "mode": "synthetic_only",
        "provider_calls": 0,
        "model_calls": 0,
        "cases": [
            {
                "scenario": name,
                "feedback": feedback_from_pool(
                    build_pool(
                        value,
                        rng_seed="synthetic-demo-not-a-production-secret",
                        policy=policy,
                    )
                ).model_dump(mode="json"),
            }
            for name, value, policy in cases
        ],
        "real_sample_gate": {
            "status": "blocked",
            "reason": "spike_retained_aggregates_not_normalized_candidates",
            "mcp_ordering_verified": False,
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic", action="store_true", required=True)
    parser.parse_args()
    print(json.dumps(synthetic_report(), indent=2))
