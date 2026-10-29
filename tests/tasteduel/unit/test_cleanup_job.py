"""Unattended cleanup must fail closed before database access and redact errors."""

from datetime import UTC, datetime
import json
from contextlib import contextmanager
from types import SimpleNamespace

from tasteduel import cleanup


def test_expired_operating_window_never_resolves_database(monkeypatch, capsys):
    monkeypatch.setenv("TASTEDUEL_OPS_REVIEWED_THROUGH_UTC", "2000-01-01T00:00:00Z")
    def forbidden():
        raise AssertionError("Database configuration must not be resolved")
    monkeypatch.setattr(cleanup, "Settings", forbidden)
    assert cleanup.main() == 2
    assert json.loads(capsys.readouterr().out)["reason_code"] == "REVIEWED_OPERATING_WINDOW_ENDED"


class DemoClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 10, 29, tzinfo=UTC)


def test_missing_cost_review_blocks_before_database(monkeypatch, capsys):
    monkeypatch.setattr(cleanup, "datetime", DemoClock)
    monkeypatch.setenv("TASTEDUEL_OPS_REVIEWED_THROUGH_UTC", "2026-11-07T04:45:00Z")
    monkeypatch.delenv("TASTEDUEL_OPS_COST_REVIEW_HASH", raising=False)
    assert cleanup.main() == 2
    assert json.loads(capsys.readouterr().out)["reason_code"] == "MATCHING_REVIEWED_COST_HASH_REQUIRED"


def test_cleanup_exception_never_prints_credentials(monkeypatch, capsys):
    monkeypatch.setattr(cleanup, "datetime", DemoClock)
    monkeypatch.setenv("TASTEDUEL_OPS_REVIEWED_THROUGH_UTC", "2026-11-07T04:45:00Z")
    monkeypatch.setattr(cleanup, "reviewed_mutation", lambda value: None)
    def rejected(*args, **kwargs):
        raise RuntimeError("PRIVATE_DATABASE_PASSWORD_AND_NICKNAME")
    monkeypatch.setattr(cleanup, "resolve_database_url", rejected)
    assert cleanup.main() == 2
    output = capsys.readouterr().out
    assert "PRIVATE" not in output
    assert json.loads(output)["reason_code"] == "CLEANUP_FAILED"


def test_cleanup_logs_committed_deletions_and_remaining_backlog(monkeypatch, capsys):
    monkeypatch.setattr(cleanup, "datetime", DemoClock)
    monkeypatch.setenv("TASTEDUEL_OPS_REVIEWED_THROUGH_UTC", "2026-11-07T04:45:00Z")
    monkeypatch.setattr(cleanup, "reviewed_mutation", lambda value: None)
    monkeypatch.setattr(cleanup, "resolve_database_url", lambda *args, **kwargs: "synthetic")
    state = {"commits": 0, "purges": 0, "disposed": False}
    @contextmanager
    def transaction():
        yield SimpleNamespace(execute=lambda *args: SimpleNamespace(scalar_one=lambda: 0))
        state["commits"] += 1
    engine = SimpleNamespace(begin=transaction, dispose=lambda: state.update(disposed=True))
    monkeypatch.setattr(cleanup, "database_engine", lambda *args, **kwargs: engine)
    def purge(db, *, execute=False):
        state["purges"] += 1
        return {"bounded_counts": {"sessions": 2 if execute and state["purges"] == 1 else 0},
                "oldest_expired_session_seconds": 0, "batch_deadline_reached": False}
    monkeypatch.setattr(cleanup, "purge", purge)
    assert cleanup.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["deleted_counts"] == {"sessions": 2}
    assert output["remaining_bounded_counts"] == {"sessions": 0}
    assert output["status"] == "PASS"
    assert state == {"commits": 3, "purges": 3, "disposed": True}
