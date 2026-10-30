"""Synthetic-only audit tests: diagnostics remain aggregate, fail closed and honest."""

from dataclasses import replace
import importlib.util
import json
from pathlib import Path

from tasteduel.application.pool_preparation import PreparedPool
from tasteduel.application.pool_feedback import feedback_from_pool
from tasteduel.domain.duel_pool import build_pool
from tasteduel.ports.qloo import EntityMetadata, QlooResult, RankedCandidate

from .synthetic import snapshot

spec = importlib.util.spec_from_file_location(
    "quality_audit", Path(__file__).resolve().parents[3] / "scripts/tasteduel_round_quality.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def audit(value):
    pool = build_pool(value, rng_seed="synthetic-private-seed")
    result = QlooResult(
        status="ok",
        candidates=tuple(
            RankedCandidate(
                EntityMetadata(row.id, row.name, row.domain, row.image_url, row.image_rights_verified),
                row.affinity,
                row.position - 1,
            )
            for row in value.candidates
        ),
    )
    return module.audit_prepared_pool(result, PreparedPool(feedback_from_pool(pool), pool, value))


def test_ready_report_is_aggregate_only_and_does_not_claim_human_calibration():
    value = snapshot()
    report = audit(value)
    assert report["path_no_repeat"] and report["path_strict_verified_winners"]
    assert report["path_same_type"] and report["path_sides_balanced"]
    assert report["cross_domain"] and report["path_owned_fallback_count"] == 10
    assert not report["human_surprise_calibrated"] and not report["human_difficulty_calibrated"]
    encoded = json.dumps(report)
    for row in value.candidates:
        assert row.name not in encoded and str(row.id) not in encoded
    assert value.context_hash not in encoded and "winner_side" not in encoded


def test_duplicate_names_and_unlicensed_metadata_are_counted_without_fetching():
    value = snapshot()
    rows = list(value.candidates)
    rows[0] = replace(rows[0], name="Repeated synthetic", image_url="https://example.invalid/image")
    rows[1] = replace(rows[1], name=" repeated synthetic ")
    report = audit(replace(value, candidates=tuple(rows)))
    assert report["duplicate_normalized_name_rows"] == 2
    assert report["candidate_rejections"]["ambiguous_name"] == 2
    assert report["image_metadata_count"] == 1 and report["image_rights_verified_count"] == 0
    assert report["path_owned_fallback_count"] == 10


def test_ties_never_pass_feasibility_or_verified_winner_check():
    value = snapshot()
    report = audit(replace(value, candidates=tuple(replace(row, affinity=1.0) for row in value.candidates)))
    assert report["pool_status"] == "insufficient_coverage"
    assert report["pair_rejections"] == {"tied_score": 190}
    assert not report["path_no_repeat"] and not report["path_strict_verified_winners"]
    assert report["path_round_count"] == 0
