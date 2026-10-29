"""Fixed unattended cleanup. No HTTP endpoint, provider calls or SQL arguments."""

from datetime import UTC, datetime
import json
import os

from sqlalchemy import text

from tasteduel.adapters.database_secrets import resolve_database_url
from tasteduel.config import Settings
from tasteduel.operations import OperationBlocked, purge, reviewed_mutation
from tasteduel.persistence.db import database_engine


def main():
    engine = None
    try:
        horizon = datetime.fromisoformat(os.environ["TASTEDUEL_OPS_REVIEWED_THROUGH_UTC"].replace("Z", "+00:00"))
        if datetime.now(UTC) >= horizon:
            raise OperationBlocked("REVIEWED_OPERATING_WINDOW_ENDED")
        reviewed_mutation(os.environ.get("TASTEDUEL_OPS_COST_REVIEW_HASH"))
        settings = Settings()
        engine = database_engine(resolve_database_url(settings, migration=True), migration=True, mode=settings.database_mode)
        facts = None
        deleted = {}
        for _ in range(3):
            if datetime.now(UTC) >= horizon:
                break
            with engine.begin() as db:
                facts = purge(db, execute=True)
            for table, count in facts["bounded_counts"].items():
                deleted[table] = deleted.get(table, 0) + count
            if not any(facts["bounded_counts"].values()):
                break
        # Check backlog after the final committed batch, not dispatch success.
        with engine.begin() as db:
            backlog = purge(db)
            expired_budgets = db.execute(text("SELECT count(*) FROM (SELECT 1 FROM tasteduel.usage_budgets WHERE expires_at<=clock_timestamp() LIMIT 101) bounded")).scalar_one()
        remaining = any(backlog["bounded_counts"].values()) or expired_budgets > 0
        failed = backlog["batch_deadline_reached"] or backlog["oldest_expired_session_seconds"] > 1800
        status = "FAIL" if failed else "BACKLOG" if remaining else "PASS"
        print(json.dumps({"event": "cleanup", "status": status,
            "deleted_counts": deleted,
            "oldest_expired_session_seconds": backlog["oldest_expired_session_seconds"],
            "remaining_bounded_counts": backlog["bounded_counts"], "expired_budget_count_cap": expired_budgets,
            "backups_rewritten": False}))
        return 2 if failed else 0
    except Exception as failure:
        code = str(failure) if isinstance(failure, OperationBlocked) else "CLEANUP_FAILED"
        print(json.dumps({"event": "cleanup", "status": "FAIL", "reason_code": code}))
        return 2
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
