"""One reviewed candidate-only Vertex allowance; never reset usage or expiry.

Default execution inspects numeric/date metadata and writes an exclusive ignored
snapshot. Mutation additionally requires the explicit flag, matching active
snapshot, fresh approved cost, applied closure plan and live API limit ten.
Host-only connector dependency: cloud-sql-python-connector[psycopg]==1.23.0.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import UTC, datetime
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / ".data/tasteduel-cloud-review"
PROJECT = "project-bb13ecd8-9d67-408d-9a7"
REGION = "asia-south1"
MODEL = "gemini-3.1-flash-lite"
SCOPE = hashlib.sha256(f"vertex:{PROJECT}:{MODEL}".encode()).hexdigest()
REQUEST = "vertex-requests-day"
TOKENS = "vertex-tokens-day"
OPERATION = "candidate-vertex-eight-to-ten"
JOURNAL = "candidate-eight-to-ten-allowance-journal.json"


class AllowanceBlocked(Exception):
    """Operator-visible failures contain fixed codes only."""


def private_path(path: Path) -> Path:
    value = path.resolve()
    if not value.is_relative_to(PRIVATE.resolve()) or value == PRIVATE.resolve():
        raise AllowanceBlocked("PRIVATE_ARTIFACT_BOUNDARY_REQUIRED")
    return value


def stamp(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise AllowanceBlocked("ALLOWANCE_TIMESTAMP_INVALID")
    return value.astimezone(UTC).isoformat()


def snapshot(db, *, lock=False) -> dict:
    db.execute(text("SET LOCAL lock_timeout = '500ms'"))
    db.execute(text("SET LOCAL statement_timeout = '1000ms'"))
    db.execute(text("SELECT set_config('app.usage_scope', :scope, true)"), {"scope": SCOPE})
    rows = db.execute(text("""SELECT bucket,used,limit_value,window_start,expires_at
        FROM tasteduel.usage_budgets WHERE scope_hash=:scope
        AND bucket IN ('vertex-requests-day','vertex-tokens-day')
        ORDER BY bucket""" + (" FOR UPDATE" if lock else "")), {"scope": SCOPE}).mappings().all()
    if len(rows) != 2 or {row["bucket"] for row in rows} != {REQUEST, TOKENS}:
        raise AllowanceBlocked("EXISTING_MODEL_COUNTERS_REQUIRED")
    return {"version": 1, "operation": OPERATION, "rows": {
        row["bucket"]: {"used": row["used"], "limit": row["limit_value"],
                        "window_start": stamp(row["window_start"]), "expires_at": stamp(row["expires_at"])}
        for row in rows}}


def validate_expected(value: dict) -> None:
    if (not isinstance(value, dict) or set(value) != {"version", "operation", "rows"}
            or type(value["version"]) is not int or value["version"] != 1
            or value["operation"] != OPERATION or not isinstance(value["rows"], dict)
            or set(value["rows"]) != {REQUEST, TOKENS}):
        raise AllowanceBlocked("EXPECTED_SNAPSHOT_INVALID")
    for row in value["rows"].values():
        if (not isinstance(row, dict) or set(row) != {"used", "limit", "window_start", "expires_at"}
                or type(row["used"]) is not int or type(row["limit"]) is not int
                or not 0 <= row["used"] <= row["limit"]):
            raise AllowanceBlocked("EXPECTED_SNAPSHOT_INVALID")
        try:
            start = datetime.fromisoformat(row["window_start"])
            end = datetime.fromisoformat(row["expires_at"])
            if start.tzinfo is None or end.tzinfo is None or end <= start:
                raise ValueError()
        except (TypeError, ValueError):
            raise AllowanceBlocked("EXPECTED_SNAPSHOT_INVALID") from None
    if (value["rows"][REQUEST]["used"] != 8 or value["rows"][REQUEST]["limit"] != 8
            or value["rows"][TOKENS]["limit"] != 500000):
        raise AllowanceBlocked("ONLY_EXHAUSTED_EIGHT_TO_TEN_ALLOWED")
    for key in ("window_start", "expires_at"):
        if value["rows"][REQUEST][key] != value["rows"][TOKENS][key]:
            raise AllowanceBlocked("MATCHING_EXISTING_DAILY_WINDOWS_REQUIRED")


def adjust(db, expected: dict) -> dict:
    """Caller owns commit; any failure must roll back this transaction."""
    validate_expected(expected)
    before = snapshot(db, lock=True)
    if before != expected:
        raise AllowanceBlocked("MODEL_COUNTER_CHANGED_AFTER_INSPECTION")
    row = before["rows"][REQUEST]
    now = db.execute(text("SELECT clock_timestamp()")).scalar_one()
    if any(datetime.fromisoformat(item["expires_at"]) <= now for item in before["rows"].values()):
        raise AllowanceBlocked("ACTIVE_UNCHANGED_EXHAUSTED_WINDOW_REQUIRED")
    result = db.execute(text("""UPDATE tasteduel.usage_budgets SET limit_value=10
        WHERE scope_hash=:scope AND bucket='vertex-requests-day'
        AND used=8 AND limit_value=8 AND window_start=:window AND expires_at=:expiry
        AND expires_at>clock_timestamp() RETURNING used"""),
        {"scope": SCOPE, "window": datetime.fromisoformat(row["window_start"]),
         "expiry": datetime.fromisoformat(row["expires_at"])}).all()
    if len(result) != 1 or result[0][0] != 8:
        raise AllowanceBlocked("ACTIVE_UNCHANGED_EXHAUSTED_WINDOW_REQUIRED")
    after = snapshot(db)
    approved_after = json.loads(json.dumps(before))
    approved_after["rows"][REQUEST]["limit"] = 10
    if after != approved_after:
        raise AllowanceBlocked("ALLOWANCE_PRESERVATION_CHECK_FAILED")
    return after


def verify_release(directory: Path, plan_hash: str, cost: dict) -> dict:
    import tasteduel_foundation_plan as foundation

    if not re.fullmatch(r"[a-f0-9]{64}", plan_hash):
        raise AllowanceBlocked("EXACT_REVIEWED_PLAN_HASH_REQUIRED")
    foundation.approved_variables(cost)
    directory = private_path(directory)
    review = json.loads((directory / "review.json").read_text(encoding="utf-8"))
    approval = json.loads((directory / "independent-approval.json").read_text(encoding="utf-8"))
    applied = json.loads((directory / "apply-journal.json").read_text(encoding="utf-8"))
    if (review.get("status") != "REVIEWABLE" or approval.get("independent_review") != "PASS"
            or applied.get("status") != "APPLIED" or applied.get("exit_code") != 0
            or review.get("reviewed_total_usd") != cost["reviewed_total_usd"]
            or applied.get("public_product_access") is not False):
        raise AllowanceBlocked("APPLIED_REVIEWED_CANDIDATE_PLAN_REQUIRED")
    for record in (review, approval, applied):
        if record.get("phase") != "candidate-closure-budget" or record.get("plan_sha256") != plan_hash:
            raise AllowanceBlocked("CANDIDATE_CLOSURE_PLAN_MISMATCH")
        for key in ("source_sha256", "image_source_sha"):
            if record.get(key) != review.get(key) or not re.fullmatch(r"[a-f0-9]{40,64}", str(record.get(key))):
                raise AllowanceBlocked("CANDIDATE_CLOSURE_PLAN_MISMATCH")
    if hashlib.sha256((directory / "release.tfplan").read_bytes()).hexdigest() != plan_hash:
        raise AllowanceBlocked("SAVED_PLAN_HASH_CHANGED")
    return {"phase": "candidate-closure-budget", "plan_sha256": plan_hash,
            "reviewed_total_usd": cost["reviewed_total_usd"]}


def verify_service(record: dict) -> None:
    try:
        containers = record["spec"]["template"]["spec"]["containers"]
        env = containers[0]["env"]
        values = {item["name"]: item.get("value") for item in env}
        ready = record["status"]["latestReadyRevisionName"]
        traffic = record["status"]["traffic"]
        valid = (record["metadata"]["name"] == "tasteduel-api" and len(containers) == 1
                 and len(values) == len(env) and values.get("TASTEDUEL_VERTEX_REQUESTS_PER_DAY") == "10"
                 and values.get("TASTEDUEL_VERTEX_TOKENS_PER_DAY") == "500000"
                 and values.get("TASTEDUEL_QLOO_REQUESTS_PER_DAY") == "12"
                 and ready == record["status"]["latestCreatedRevisionName"]
                 and len(traffic) == 1 and traffic[0].get("percent") == 100
                 and traffic[0].get("revisionName") == ready)
    except (KeyError, IndexError, TypeError):
        valid = False
    if not valid:
        raise AllowanceBlocked("READY_API_WITH_REVIEWED_TEN_LIMIT_REQUIRED")


def service_check() -> None:
    executable = shutil.which("gcloud")
    if not executable:
        raise AllowanceBlocked("GCLOUD_REQUIRED_FOR_SERVICE_CHECK")
    response = subprocess.run([executable, "run", "services", "describe", "tasteduel-api",
                               "--project=" + PROJECT, "--region=" + REGION, "--format=json"],
                              capture_output=True, text=True, timeout=30)
    if response.returncode != 0:
        raise AllowanceBlocked("CURRENT_API_CONFIGURATION_CHECK_FAILED")
    verify_service(json.loads(response.stdout))


@contextmanager
def cloud_engine():
    sys.path.insert(0, str(ROOT / "apps/api/src"))
    from tasteduel.config import CLOUD_SQL_CONNECTION, validate_database_url

    if version("cloud-sql-python-connector") != "1.23.0":
        raise AllowanceBlocked("PINNED_HOST_CONNECTOR_REQUIRED")
    from google.cloud import secretmanager
    from google.cloud.sql.connector import Connector, IPTypes

    reference = f"projects/{PROJECT}/secrets/tasteduel-migrate-database-url/versions/1"
    with secretmanager.SecretManagerServiceClient() as client:
        payload = client.access_secret_version(request={"name": reference}, retry=None, timeout=5).payload.data.decode("utf-8")
    validate_database_url(payload, mode="cloud_sql", migration=True)
    password = make_url(payload).password
    del payload
    with Connector(refresh_strategy="LAZY") as connector:
        engine = create_engine("postgresql+psycopg://", poolclass=NullPool, hide_parameters=True,
            creator=lambda: connector.connect(CLOUD_SQL_CONNECTION, "psycopg", user="tasteduel_migrator",
                password=password, db="tasteduel", ip_type=IPTypes.PUBLIC, timeout=15,
                options="-csearch_path=tasteduel,pg_catalog"))
        try:
            with engine.connect() as db:
                identity = db.execute(text("SELECT current_database(),current_user")).one()
                if tuple(identity) != ("tasteduel", "tasteduel_migrator"):
                    raise AllowanceBlocked("EXACT_DATABASE_MIGRATION_IDENTITY_REQUIRED")
            yield engine
        finally:
            engine.dispose()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--execute-reviewed-allowance", action="store_true")
    parser.add_argument("--cost", type=Path)
    parser.add_argument("--release-directory", type=Path)
    parser.add_argument("--plan-sha256")
    args = parser.parse_args(argv)
    journal = None
    journal_path = None
    journal_owned = False
    committed = False
    try:
        destination = private_path(args.snapshot)
        if not args.execute_reviewed_allowance:
            if destination.exists():
                raise AllowanceBlocked("INSPECTION_SNAPSHOT_ALREADY_EXISTS")
            with cloud_engine() as engine, engine.connect() as db:
                db.execute(text("SET TRANSACTION READ ONLY"))
                expected = snapshot(db)
            validate_expected(expected)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("x", encoding="utf-8") as handle:
                json.dump(expected, handle, indent=2)
            print(json.dumps({"status": "INSPECTED", "mutation": False, "used": 8, "limit": 8,
                              "payload_files": False}))
            return 0
        if not all((args.cost, args.release_directory, args.plan_sha256)):
            raise AllowanceBlocked("COST_AND_APPLIED_PLAN_REQUIRED")
        expected = json.loads(destination.read_text(encoding="utf-8"))
        validate_expected(expected)
        cost_path = private_path(args.cost)
        references = verify_release(args.release_directory, args.plan_sha256,
                                    json.loads(cost_path.read_text(encoding="utf-8")))
        service_check()
        journal_path = PRIVATE / JOURNAL
        journal = {"status": "STARTED", "operation": OPERATION, **references,
                   "snapshot_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                   "started_at_utc": datetime.now(UTC).isoformat(), "automatic_retry": False}
        with journal_path.open("x", encoding="utf-8") as handle:
            json.dump(journal, handle, indent=2)
        journal_owned = True
        with cloud_engine() as engine:
            with engine.begin() as db:
                after = adjust(db, expected)
            committed = True
            with engine.connect() as db:
                verified = snapshot(db)
            if verified != after:
                raise AllowanceBlocked("POST_COMMIT_METADATA_CHANGED_REVIEW_REQUIRED")
        journal.update(status="APPLIED", committed=True, before=expected, after=after,
                       used_preserved=True, window_and_expiry_preserved=True, token_row_preserved=True,
                       completed_at_utc=datetime.now(UTC).isoformat())
        journal_path.write_text(json.dumps(journal, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "APPLIED", "used": 8, "before_limit": 8, "after_limit": 10,
                          "usage_reset": False, "window_extended": False, "automatic_retry": False}))
        return 0
    except Exception as failure:
        # Never stringify SDK/SQL/credential-bearing exceptions or print tracebacks.
        if journal_owned and journal is not None and journal_path is not None:
            journal.update(status="FAILED_REQUIRES_RECOVERY", committed=committed,
                           completed_at_utc=datetime.now(UTC).isoformat())
            journal_path.write_text(json.dumps(journal, indent=2) + "\n", encoding="utf-8")
        code = str(failure) if isinstance(failure, AllowanceBlocked) else "ALLOWANCE_OPERATION_FAILED"
        print(json.dumps({"status": "BLOCKED", "reason_code": code, "automatic_retry": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
