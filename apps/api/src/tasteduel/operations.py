"""Fixed, role-restricted release operations; no provider calls or arbitrary SQL.

One-shot migration job commands: migrate, purge-expired, promote-public-budget.
Inspection is the default. All mutations require --execute-reviewed-operation;
production requires a matching reviewed cost hash and unexpired operating window.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import logging
import os
import re
import subprocess
import time

from sqlalchemy import text

from tasteduel.persistence.models import Base

PROJECT = "project-bb13ecd8-9d67-408d-9a7"
MODEL = "gemini-3.1-flash-lite"
VERTEX_SCOPE = hashlib.sha256(f"vertex:{PROJECT}:{MODEL}".encode()).hexdigest()
OWNED = frozenset({"sessions", "entities", "games", "generation_reservations", "ranking_snapshots",
    "snapshot_candidates", "curation_receipts", "private_pairs", "delivered_rounds", "round_contestants",
    "answers", "game_results", "challenges", "challenge_rounds", "challenge_plays", "discoveries",
    "provider_cache", "usage_counters", "mutation_receipts", "product_events"})


class OperationBlocked(Exception):
    pass


def safe_event(event, *, status, elapsed_ms, mode=None):
    if event not in {"generation", "request_error"} or type(status) is not int or not 100 <= status <= 599:
        raise ValueError("Invalid operational event")
    facts = {"event": event, "status": status, "elapsed_ms": max(0, min(120000, int(elapsed_ms)))}
    if mode in {"genuine_agent", "deterministic_qloo", "fixture"}:
        facts["mode"] = mode
    logging.getLogger("uvicorn.error").info("%s", json.dumps(facts, separators=(",", ":")))


def migrator(db):
    identity = db.execute(text("SELECT current_user,session_user")).one()
    if tuple(identity) != ("tasteduel_migrator", "tasteduel_migrator"):
        raise OperationBlocked("MIGRATION_IDENTITY_REQUIRED")
    db.execute(text("SET LOCAL lock_timeout='500ms'"))
    db.execute(text("SET LOCAL statement_timeout='5000ms'"))
    if not db.execute(text("SELECT pg_try_advisory_xact_lock(781139,19)")).scalar_one():
        raise OperationBlocked("MAINTENANCE_ALREADY_RUNNING")


def _unreferenced(table):
    clauses = []
    for child in Base.metadata.tables.values():
        for constraint in child.foreign_key_constraints:
            if constraint.referred_table is table:
                if table.name == "games" and child.name in {"challenge_plays", "product_events"}:
                    continue  # Expired game deletion cascades these same-game rows only.
                predicates = " AND ".join(f'c."{part.parent.name}"=t."{part.column.name}"' for part in constraint.elements)
                clauses.append(f'NOT EXISTS(SELECT 1 FROM tasteduel."{child.name}" c WHERE {predicates})')
    return " AND ".join(clauses) or "true"


def purge(db, *, execute=False):
    migrator(db)
    tables = [table for table in reversed(Base.metadata.sorted_tables)
              if table.name in OWNED and table.name != "challenge_plays"]
    counts = {}
    started = time.monotonic()
    if execute:
        db.execute(text("""INSERT INTO tasteduel.challenge_tombstones(slug_hash,reason,expires_at)
            SELECT c.slug_hash,CASE WHEN c.revoked_at IS NOT NULL OR s.revoked_at IS NOT NULL
              THEN 'revoked' ELSE 'expired' END,clock_timestamp()+interval '7 days'
            FROM tasteduel.challenges c JOIN tasteduel.sessions s ON s.id=c.session_id
            WHERE tasteduel.maintenance_deletable('challenges',to_jsonb(c))
            ORDER BY c.session_id,c.id LIMIT 100 ON CONFLICT(slug_hash) DO NOTHING"""))
    for _ in range(3 if execute else 1):
        for table in tables:
            if time.monotonic()-started > 25:
                raise OperationBlocked("MAINTENANCE_DEADLINE")
            predicate = f"tasteduel.maintenance_deletable('{table.name}',to_jsonb(t))"
            if execute:
                # Foreign-key references are checked before deletion; oversized batches
                # leave parents for the next run rather than cascading active rows.
                predicate += " AND " + _unreferenced(table)
                if table.name == "challenges":
                    predicate += " AND EXISTS(SELECT 1 FROM tasteduel.challenge_tombstones z WHERE z.slug_hash=t.slug_hash)"
                ordering = "t.id" if table.name == "sessions" else "t.session_id,t.id"
                result = db.execute(text(f'''DELETE FROM tasteduel."{table.name}" WHERE id IN
                    (SELECT t.id FROM tasteduel."{table.name}" t WHERE {predicate}
                     ORDER BY {ordering} LIMIT 100)'''))
                counts[table.name] = counts.get(table.name, 0)+result.rowcount
            else:
                counts[table.name] = db.execute(text(f'''SELECT count(*) FROM
                    (SELECT 1 FROM tasteduel."{table.name}" t WHERE {predicate} LIMIT 101) bounded''')).scalar_one()
    if execute:
        counts["challenge_tombstones"] = db.execute(text("""DELETE FROM tasteduel.challenge_tombstones
            WHERE slug_hash IN(SELECT slug_hash FROM tasteduel.challenge_tombstones
              WHERE expires_at<=clock_timestamp() ORDER BY slug_hash LIMIT 100)""")).rowcount
    return {"operation": "purge-expired", "executed": execute, "bounded_counts": counts,
            "count_cap": 300 if execute else 101, "counts_exclude_cascades": True,
            "backups_rewritten": False}


def budget_snapshot(db, *, lock=False):
    migrator(db)
    records = db.execute(text("""SELECT scope_hash,bucket,used,limit_value,window_start,expires_at
        FROM tasteduel.usage_budgets WHERE
        (scope_hash=:vertex AND bucket IN('vertex-requests-day','vertex-tokens-day'))
        OR bucket='qloo-requests-day' ORDER BY scope_hash,bucket""" + (" FOR UPDATE" if lock else "")),
        {"vertex": VERTEX_SCOPE}).mappings().all()
    if len(records) != 3 or {row["bucket"] for row in records} != {
            "vertex-requests-day", "vertex-tokens-day", "qloo-requests-day"}:
        raise OperationBlocked("UNIQUE_EXISTING_PROVIDER_COUNTERS_REQUIRED")
    return {row["bucket"]: dict(row) for row in records}


def budget_digest(rows):
    # The private digest binds opaque Qloo scope without printing the fingerprint.
    return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()


def promote_budget(db, *, expected_digest=None, execute=False):
    rows = budget_snapshot(db, lock=execute)
    digest = budget_digest(rows)
    if not execute:
        return {"operation": "promote-public-budget", "executed": False, "snapshot_sha256": digest,
                "counts": {key: {"used": row["used"], "limit": row["limit_value"]} for key, row in rows.items()}}
    if not re.fullmatch(r"[a-f0-9]{64}", expected_digest or "") or digest != expected_digest:
        raise OperationBlocked("EXACT_PROVIDER_SNAPSHOT_REQUIRED")
    now = db.execute(text("SELECT clock_timestamp()")).scalar_one()
    for bucket, old, new in (("vertex-requests-day", 10, 50), ("qloo-requests-day", 12, 100)):
        row = rows[bucket]
        if row["used"] != 10 or row["limit_value"] != old or row["expires_at"] <= now:
            raise OperationBlocked("UNCHANGED_TEN_CALL_ACTIVE_BASELINE_REQUIRED")
    token = rows["vertex-tokens-day"]
    if token["limit_value"] != 500000 or token["expires_at"] <= now:
        raise OperationBlocked("UNCHANGED_ACTIVE_TOKEN_BUDGET_REQUIRED")
    for bucket, old, new in (("vertex-requests-day", 10, 50), ("qloo-requests-day", 12, 100)):
        row = rows[bucket]
        changed = db.execute(text("""UPDATE tasteduel.usage_budgets SET limit_value=:new
            WHERE scope_hash=:scope AND bucket=:bucket AND used=10 AND limit_value=:old
              AND window_start=:window AND expires_at=:expiry AND expires_at>clock_timestamp()
            RETURNING used"""), {"new": new, "scope": row["scope_hash"], "bucket": bucket,
                "old": old, "window": row["window_start"], "expiry": row["expires_at"]}).all()
        if len(changed) != 1 or changed[0][0] != 10:
            raise OperationBlocked("PUBLIC_BUDGET_CHANGED_DURING_PROMOTION")
    after = budget_snapshot(db)
    for bucket in rows:
        expected = dict(rows[bucket])
        if bucket != "vertex-tokens-day":
            expected["limit_value"] = 50 if bucket.startswith("vertex") else 100
        if after[bucket] != expected:
            raise OperationBlocked("PUBLIC_BUDGET_PRESERVATION_FAILED")
    return {"operation": "promote-public-budget", "executed": True, "usage_reset": False,
            "window_extended": False, "token_budget_unchanged": True,
            "counts": {key: {"used": row["used"], "limit": row["limit_value"]} for key, row in after.items()}}


def admission_available(engine, *, qloo_scope, project, model, qloo_limit, model_limit, token_limit):
    if not re.fullmatch(r"[a-f0-9]{64}", qloo_scope or ""):
        return False
    vertex_scope = hashlib.sha256(f"vertex:{project}:{model}".encode()).hexdigest()
    with engine.begin() as db:
        db.execute(text("SET LOCAL statement_timeout='1000ms'"))
        for scope, bucket, configured, needed in ((qloo_scope, "qloo-requests-day", qloo_limit, 1),
                (vertex_scope, "vertex-requests-day", model_limit, 1),
                (vertex_scope, "vertex-tokens-day", token_limit, 10512)):
            db.execute(text("SELECT set_config('app.usage_scope',:scope,true)"), {"scope": scope})
            row = db.execute(text("""SELECT used,limit_value,expires_at>clock_timestamp() active
                FROM tasteduel.usage_budgets WHERE scope_hash=:scope AND bucket=:bucket"""),
                {"scope": scope, "bucket": bucket}).mappings().one_or_none()
            if row and row["active"] and row["used"]+needed > min(row["limit_value"], configured):
                return False
        db.execute(text("SELECT set_config('app.provider_scope',:scope,true)"), {"scope": qloo_scope})
        blocked = db.execute(text("""SELECT auth_blocked OR coalesce(open_until>clock_timestamp(),false)
            FROM tasteduel.provider_controls WHERE scope_hash=:scope"""), {"scope": qloo_scope}).scalar_one_or_none()
        return not blocked


def reviewed_mutation(cost_hash):
    if (not re.fullmatch(r"[a-f0-9]{64}", cost_hash or "")
            or cost_hash != os.getenv("TASTEDUEL_OPS_COST_REVIEW_HASH")):
        raise OperationBlocked("MATCHING_REVIEWED_COST_HASH_REQUIRED")
    try:
        horizon = datetime.fromisoformat(os.environ["TASTEDUEL_OPS_REVIEWED_THROUGH_UTC"].replace("Z", "+00:00"))
        if horizon.tzinfo is None or not datetime.now(UTC) < horizon <= datetime(2026, 11, 7, 4, 45, tzinfo=UTC):
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise OperationBlocked("REVIEWED_OPERATING_WINDOW_REQUIRED") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("migrate", "purge-expired", "promote-public-budget"))
    parser.add_argument("--execute-reviewed-operation", action="store_true")
    parser.add_argument("--cost-review-sha256")
    parser.add_argument("--expected-snapshot-sha256")
    args = parser.parse_args(argv)
    engine = None
    try:
        if args.execute_reviewed_operation:
            reviewed_mutation(args.cost_review_sha256)
        if args.command == "migrate":
            if not args.execute_reviewed_operation:
                raise OperationBlocked("MIGRATION_REQUIRES_EXPLICIT_REVIEWED_EXECUTION")
            result = subprocess.run(["alembic", "-c", "apps/api/tasteduel-alembic.ini", "upgrade", "head"],
                                    capture_output=True, text=True, timeout=240)
            if result.returncode != 0:
                raise OperationBlocked("MIGRATION_FAILED_REVIEW_REQUIRED")
            facts = {"operation": "migrate", "schema_revision": "td0011", "executed": True}
        else:
            from tasteduel.adapters.database_secrets import resolve_database_url
            from tasteduel.config import Settings
            from tasteduel.persistence.db import database_engine

            settings = Settings()
            engine = database_engine(resolve_database_url(settings, migration=True), migration=True, mode=settings.database_mode)
            with engine.begin() as db:
                facts = (purge(db, execute=args.execute_reviewed_operation) if args.command == "purge-expired"
                         else promote_budget(db, expected_digest=args.expected_snapshot_sha256, execute=args.execute_reviewed_operation))
        print(json.dumps({"status": "PASS", **facts}))
        return 0
    except Exception as failure:
        code = str(failure) if isinstance(failure, OperationBlocked) else "OPERATION_FAILED_REVIEW_REQUIRED"
        print(json.dumps({"status": "BLOCKED", "reason_code": code, "automatic_retry": False}))
        return 2
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
