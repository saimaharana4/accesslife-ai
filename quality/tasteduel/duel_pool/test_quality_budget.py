"""Synthetic transport-budget checks; no live key, ADC or provider access."""

import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "quality_live_budget", Path(__file__).resolve().parents[3] / "scripts/tasteduel_quality_live.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def budget_file(tmp_path, *, dispatched=0, closed=False):
    path = tmp_path / "budget.json"
    path.write_text(json.dumps({"ceiling": 8, "dispatched": dispatched, "closed": closed, "events": []}))
    return path


def test_send_is_durably_consumed_before_transport_and_cannot_exceed_ceiling(tmp_path):
    path = budget_file(tmp_path, dispatched=7)
    budget = module.QualityBudget(path)
    budget.dispatch("/search")
    assert json.loads(path.read_text())["dispatched"] == 8
    resumed = module.QualityBudget(path)
    with pytest.raises(RuntimeError, match="exhausted"):
        resumed.dispatch("/v2/insights")
    assert json.loads(path.read_text())["dispatched"] == 8


def test_closed_budget_is_not_renewed_by_resume(tmp_path):
    with pytest.raises(RuntimeError, match="Closed"):
        module.QualityBudget(budget_file(tmp_path, closed=True))


@pytest.mark.parametrize("dispatched", [-1, 9, False, 1.5])
def test_corrupt_counter_cannot_expand_request_budget(tmp_path, dispatched):
    with pytest.raises(RuntimeError, match="unexpected"):
        module.QualityBudget(budget_file(tmp_path, dispatched=dispatched))


def test_unapproved_operation_never_dispatches_or_writes_payload(tmp_path):
    path = budget_file(tmp_path)
    budget = module.QualityBudget(path)
    with pytest.raises(RuntimeError, match="exhausted"):
        budget.dispatch("/unapproved")
    assert json.loads(path.read_text())["dispatched"] == 0
