"""Real local SQL guards for a one-off allowance; no cloud/provider execution."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import tasteduel_candidate_allowance as allowance  # noqa: E402


@pytest.fixture
def counters(db_owner_engine):
    """All synthetic setup/updates are rolled back in the dedicated local DB."""
    with db_owner_engine.connect() as db:
        transaction = db.begin()
        try:
            db.execute(text("SELECT set_config('app.usage_scope', :scope, true)"), {"scope": allowance.SCOPE})
            db.execute(text("DELETE FROM tasteduel.usage_budgets WHERE scope_hash=:scope"), {"scope": allowance.SCOPE})
            db.execute(text("""INSERT INTO tasteduel.usage_budgets
                (scope_hash,bucket,window_start,expires_at,used,limit_value)
                VALUES (:scope,'vertex-requests-day',clock_timestamp()-interval '1 hour',
                  clock_timestamp()+interval '1 hour',8,8)"""), {"scope": allowance.SCOPE})
            # Copy the exact stored boundaries, not two independently sampled clocks.
            db.execute(text("""INSERT INTO tasteduel.usage_budgets
                (scope_hash,bucket,window_start,expires_at,used,limit_value)
                SELECT scope_hash,'vertex-tokens-day',window_start,expires_at,17000,500000
                FROM tasteduel.usage_budgets WHERE scope_hash=:scope AND bucket='vertex-requests-day'"""),
                {"scope": allowance.SCOPE})
            yield db
        finally:
            transaction.rollback()


def test_real_sql_only_limit_changes_and_no_second_allowance(counters):
    before = allowance.snapshot(counters)
    after = allowance.adjust(counters, before)
    expected = deepcopy(before)
    expected["rows"][allowance.REQUEST]["limit"] = 10
    assert after == expected
    assert allowance.snapshot(counters) == expected
    with pytest.raises(allowance.AllowanceBlocked, match="CHANGED_AFTER_INSPECTION"):
        allowance.adjust(counters, before)
    assert allowance.snapshot(counters) == expected


@pytest.mark.parametrize("column,value", [("used", 7), ("limit_value", 9)])
def test_real_sql_stale_request_snapshot_fails_without_changes(counters, column, value):
    before = allowance.snapshot(counters)
    counters.execute(text(f"UPDATE tasteduel.usage_budgets SET {column}=:value WHERE scope_hash=:scope AND bucket='vertex-requests-day'"),
                     {"value": value, "scope": allowance.SCOPE})
    changed = allowance.snapshot(counters)
    with pytest.raises(allowance.AllowanceBlocked, match="CHANGED_AFTER_INSPECTION"):
        allowance.adjust(counters, before)
    assert allowance.snapshot(counters) == changed


def test_real_sql_changed_token_admission_fails_without_request_mutation(counters):
    expected = allowance.snapshot(counters)
    counters.execute(text("UPDATE tasteduel.usage_budgets SET used=used+1 WHERE scope_hash=:scope AND bucket='vertex-tokens-day'"),
                     {"scope": allowance.SCOPE})
    with pytest.raises(allowance.AllowanceBlocked, match="CHANGED_AFTER_INSPECTION"):
        allowance.adjust(counters, expected)
    assert allowance.snapshot(counters)["rows"][allowance.REQUEST]["limit"] == 8


def test_real_sql_expired_window_cannot_be_reopened(counters):
    counters.execute(text("""UPDATE tasteduel.usage_budgets
        SET window_start=clock_timestamp()-interval '2 hour',expires_at=clock_timestamp()-interval '1 hour'
        WHERE scope_hash=:scope"""), {"scope": allowance.SCOPE})
    # Make both boundaries exactly equal after independent row evaluation.
    counters.execute(text("""UPDATE tasteduel.usage_budgets t
        SET window_start=r.window_start,expires_at=r.expires_at
        FROM tasteduel.usage_budgets r
        WHERE t.scope_hash=:scope AND r.scope_hash=:scope
        AND t.bucket='vertex-tokens-day' AND r.bucket='vertex-requests-day'"""), {"scope": allowance.SCOPE})
    expected = allowance.snapshot(counters)
    with pytest.raises(allowance.AllowanceBlocked, match="ACTIVE_UNCHANGED"):
        allowance.adjust(counters, expected)
    assert allowance.snapshot(counters) == expected


def test_real_sql_missing_token_row_cannot_be_manufactured(counters):
    expected = allowance.snapshot(counters)
    counters.execute(text("DELETE FROM tasteduel.usage_budgets WHERE scope_hash=:scope AND bucket='vertex-tokens-day'"),
                     {"scope": allowance.SCOPE})
    with pytest.raises(allowance.AllowanceBlocked, match="EXISTING_MODEL_COUNTERS"):
        allowance.adjust(counters, expected)
    assert counters.execute(text("SELECT limit_value FROM tasteduel.usage_budgets WHERE scope_hash=:scope AND bucket='vertex-requests-day'"),
                            {"scope": allowance.SCOPE}).scalar_one() == 8


def test_real_sql_transaction_rollback_preserves_prior_allowance(counters):
    expected = allowance.snapshot(counters)
    nested = counters.begin_nested()
    allowance.adjust(counters, expected)
    nested.rollback()
    assert allowance.snapshot(counters) == expected


def test_real_sql_rows_remain_locked_against_competing_admission(counters, db_engine):
    allowance.snapshot(counters, lock=True)
    # Synthetic rows are not committed; the identical primary key still causes
    # a real PostgreSQL lock conflict and cannot increment or replace the window.
    with db_engine.begin() as other:
        other.execute(text("SET LOCAL lock_timeout='50ms'"))
        other.execute(text("SELECT set_config('app.usage_scope', :scope, true)"), {"scope": allowance.SCOPE})
        with pytest.raises(OperationalError):
            other.execute(text("""INSERT INTO tasteduel.usage_budgets
                (scope_hash,bucket,window_start,expires_at,used,limit_value)
                VALUES (:scope,'vertex-requests-day',clock_timestamp(),clock_timestamp()+interval '1 hour',1,10)
                ON CONFLICT(scope_hash,bucket) DO UPDATE SET used=usage_budgets.used+1"""),
                {"scope": allowance.SCOPE})
    assert allowance.snapshot(counters)["rows"][allowance.REQUEST]["used"] == 8


@pytest.mark.parametrize("mutation", [
    lambda value: value.update(private_payload="forbidden"),
    lambda value: value.update(version=True),
    lambda value: value["rows"][allowance.REQUEST].update(used=True),
    lambda value: value["rows"][allowance.REQUEST].update(limit=10),
    lambda value: value["rows"][allowance.TOKENS].update(limit=1_000_000),
    lambda value: value["rows"][allowance.TOKENS].update(expires_at="2000-01-01T00:00:00"),
])
def test_expected_snapshot_rejects_extra_fields_and_widened_scope(counters, mutation):
    expected = allowance.snapshot(counters)
    mutation(expected)
    with pytest.raises(allowance.AllowanceBlocked):
        allowance.validate_expected(expected)


def service():
    return {"metadata": {"name": "tasteduel-api"},
            "spec": {"template": {"spec": {"containers": [{"env": [
                {"name": "TASTEDUEL_VERTEX_REQUESTS_PER_DAY", "value": "10"},
                {"name": "TASTEDUEL_VERTEX_TOKENS_PER_DAY", "value": "500000"},
                {"name": "TASTEDUEL_QLOO_REQUESTS_PER_DAY", "value": "12"},
            ]}]}}}, "status": {"latestReadyRevisionName": "api-reviewed", "latestCreatedRevisionName": "api-reviewed",
                                  "traffic": [{"percent": 100, "revisionName": "api-reviewed"}]}}


def test_service_configuration_requires_ready_exact_allowance_and_allocation():
    allowance.verify_service(service())
    for mutate in (
        lambda record: record["spec"]["template"]["spec"]["containers"][0]["env"][0].update(value="8"),
        lambda record: record["status"].update(latestReadyRevisionName="older"),
        lambda record: record["status"]["traffic"][0].update(percent=50),
        lambda record: record["metadata"].update(name="unrelated"),
    ):
        record = service()
        mutate(record)
        with pytest.raises(allowance.AllowanceBlocked):
            allowance.verify_service(record)


def test_default_inspection_never_adjusts_or_checks_cloud_service(tmp_path, monkeypatch):
    destination = tmp_path / "snapshot.json"
    monkeypatch.setattr(allowance, "PRIVATE", tmp_path)
    engine = Mock()
    context = Mock()
    context.__enter__ = Mock(return_value=engine)
    context.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(allowance, "cloud_engine", lambda: context)
    monkeypatch.setattr(allowance, "adjust", Mock(side_effect=AssertionError("mutation")))
    # Fail before DB access: no reusable/default overwrite may change evidence.
    destination.write_text("{}", encoding="utf-8")
    assert allowance.main(["--snapshot", str(destination)]) == 2
    engine.connect.assert_not_called()
    allowance.adjust.assert_not_called()


def test_private_boundary_and_static_secret_bearing_failure(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(allowance, "PRIVATE", tmp_path / "private")
    with pytest.raises(allowance.AllowanceBlocked):
        allowance.private_path(tmp_path / "outside.json")
    secret_failure = Mock(side_effect=RuntimeError("synthetic-private-credential-and-sql"))
    monkeypatch.setattr(allowance, "cloud_engine", secret_failure)
    assert allowance.main(["--snapshot", str(tmp_path / "private/snapshot.json")]) == 2
    assert "synthetic-private" not in capsys.readouterr().out


def test_fixed_namespace_has_no_user_or_provider_key_input():
    assert allowance.SCOPE == hashlib.sha256(
        b"vertex:project-bb13ecd8-9d67-408d-9a7:gemini-3.1-flash-lite").hexdigest()


def test_execute_requires_applied_matching_plan_before_cloud_credentials(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(allowance, "PRIVATE", tmp_path)
    snapshot = {"version": 1, "operation": allowance.OPERATION, "rows": {}}
    now = datetime.now(UTC)
    for bucket, used, limit in ((allowance.REQUEST, 8, 8), (allowance.TOKENS, 17000, 500000)):
        snapshot["rows"][bucket] = {"used": used, "limit": limit,
                                    "window_start": allowance.stamp(now-timedelta(hours=1)),
                                    "expires_at": allowance.stamp(now+timedelta(hours=1))}
    expected = tmp_path / "snapshot.json"
    expected.write_text(json.dumps(snapshot), encoding="utf-8")
    cloud = Mock(side_effect=AssertionError("no credentials before guards"))
    monkeypatch.setattr(allowance, "cloud_engine", cloud)
    assert allowance.main(["--snapshot", str(expected), "--execute-reviewed-allowance"]) == 2
    assert "COST_AND_APPLIED_PLAN_REQUIRED" in capsys.readouterr().out
    cloud.assert_not_called()
