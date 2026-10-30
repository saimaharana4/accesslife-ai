"""Operator evidence cannot become a hidden-answer or credential log surface."""

import json
import logging
from uuid import uuid4

import pytest

from tasteduel.adapters import operational_usage as ops


def test_startup_log_projects_only_numeric_admission_facts(monkeypatch, caplog):
    private_scope = "a" * 64
    seen = []

    def count(engine, scope, bucket):
        seen.append((scope, bucket))
        return 2

    monkeypatch.setattr(ops, "admitted_count", count)
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        ops.log_admission_snapshot(None, qloo_scope=private_scope, project="synthetic", model="synthetic")
    facts = json.loads(caplog.records[-1].getMessage())
    assert facts == {"event": "provider_admission_snapshot", "available": True,
                     "qloo_admitted_day": 2, "vertex_admitted_day": 2}
    assert private_scope not in caplog.text
    assert len(seen) == 2


def test_unavailable_counter_logs_no_exception_or_scope(monkeypatch, caplog):
    def unavailable(*args):
        raise RuntimeError("SYNTHETIC_PRIVATE_DIAGNOSTIC")

    monkeypatch.setattr(ops, "admitted_count", unavailable)
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        ops.log_admission_snapshot(None, qloo_scope="a" * 64, project="synthetic", model="synthetic")
    assert json.loads(caplog.records[-1].getMessage()) == {
        "event": "provider_admission_snapshot", "available": False,
    }
    assert "SYNTHETIC_PRIVATE" not in caplog.text


@pytest.mark.parametrize("scope,bucket", [("bad", "qloo-requests-day"), ("a" * 64, "private-pool")])
def test_invalid_operational_queries_fail_before_database_access(scope, bucket):
    with pytest.raises(ValueError):
        ops.admitted_count(None, scope, bucket)


def test_real_rls_counter_observation_never_reserves_or_resets_usage(db_engine):
    import hashlib
    from tasteduel.adapters.usage_budget import reserve

    scope = hashlib.sha256(str(uuid4()).encode()).hexdigest()
    with db_engine.begin() as db:
        reserve(db, scope, "qloo-requests-day", limit=12, seconds=86400, amount=2)
    assert ops.admitted_count(db_engine, scope, "qloo-requests-day") == 2
    assert ops.admitted_count(db_engine, scope, "qloo-requests-day") == 2
    other = hashlib.sha256(str(uuid4()).encode()).hexdigest()
    assert ops.admitted_count(db_engine, other, "qloo-requests-day") == 0
