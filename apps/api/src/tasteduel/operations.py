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
    # Bound the expensive lifecycle graph checks to owners with plausible
    # expiry, then use cheap indexed IDs for each child table's candidate set.
    owners = list(db.execute(text("""SELECT s.id FROM tasteduel.sessions s WHERE
        (s.revoked_at IS NOT NULL OR s.expires_at<=clock_timestamp()
         OR s.last_activity_at<=clock_timestamp()-interval '10 minutes'
         OR EXISTS(SELECT 1 FROM tasteduel.challenges c JOIN tasteduel.challenge_plays p ON p.challenge_id=c.id
           JOIN tasteduel.game_results r ON r.game_id=p.game_id
           WHERE (c.session_id=s.id OR p.session_id=s.id) AND r.created_at<=clock_timestamp()-interval '10 minutes'))
        AND NOT tasteduel.session_live(s.id) ORDER BY s.id LIMIT 100""")).scalars())
    challenges = list(db.execute(text("""SELECT c.id FROM tasteduel.challenges c
        JOIN tasteduel.sessions s ON s.id=c.session_id WHERE
        (c.revoked_at IS NOT NULL OR c.expires_at<=clock_timestamp() OR s.revoked_at IS NOT NULL
         OR s.expires_at<=clock_timestamp() OR s.last_activity_at<=clock_timestamp()-interval '10 minutes'
         OR EXISTS(SELECT 1 FROM tasteduel.challenge_plays p JOIN tasteduel.game_results r ON r.game_id=p.game_id
           WHERE p.challenge_id=c.id AND r.created_at<=clock_timestamp()-interval '10 minutes'))
        AND tasteduel.maintenance_deletable('challenges',to_jsonb(c)) ORDER BY c.session_id,c.id LIMIT 100""")).scalars())
    games = list(db.execute(text("""SELECT g.id FROM tasteduel.games g WHERE g.session_id=ANY(:owners)
        OR g.expires_at<=clock_timestamp()
        OR EXISTS(SELECT 1 FROM tasteduel.challenges c WHERE c.id=ANY(:challenges) AND c.source_game_id=g.id)
        OR EXISTS(SELECT 1 FROM tasteduel.challenge_plays p
          WHERE p.game_id=g.id AND p.challenge_id=ANY(:challenges)) ORDER BY g.id LIMIT 1000"""),
        {"owners": owners, "challenges": challenges}).scalars())
    if execute:
        # Challenge/game windows are independent of the first 100 owner IDs.
        # Persist expiry for every affected graph owner before deleting edges:
        # otherwise a completed duel outside that owner window could lose its
        # last link and regain the unlinked one-hour fallback. A game has at
        # most one replay edge, so this set is bounded by 100+100+1000+1000 IDs.
        affected = list(db.execute(text("""SELECT id FROM tasteduel.sessions WHERE id=ANY(:owners)
            UNION SELECT session_id FROM tasteduel.games WHERE id=ANY(:games)
            UNION SELECT c.session_id FROM tasteduel.challenges c WHERE c.id=ANY(:challenges)
              OR EXISTS(SELECT 1 FROM tasteduel.challenge_plays p
                WHERE p.challenge_id=c.id AND p.game_id=ANY(:games))"""),
            {"owners": owners, "games": games, "challenges": challenges}).scalars())
        # Match gameplay's sorted session locks. Re-evaluate in the following
        # statement, after any already-committing player action becomes visible.
        db.execute(text("SELECT id FROM tasteduel.sessions WHERE id=ANY(:affected) ORDER BY id FOR UPDATE"),
                   {"affected": affected}).all()
        db.execute(text("""UPDATE tasteduel.sessions SET revoked_at=clock_timestamp()
            WHERE id=ANY(:affected) AND revoked_at IS NULL AND NOT tasteduel.session_live(id)"""),
            {"affected": affected})
        db.execute(text("""INSERT INTO tasteduel.challenge_tombstones(slug_hash,reason,expires_at)
            SELECT c.slug_hash,CASE WHEN c.revoked_at IS NOT NULL OR s.revoked_at IS NOT NULL
              THEN 'revoked' ELSE 'expired' END,clock_timestamp()+interval '7 days'
            FROM tasteduel.challenges c JOIN tasteduel.sessions s ON s.id=c.session_id
            WHERE c.id=ANY(:challenges)
            ON CONFLICT(slug_hash) DO NOTHING"""), {"challenges": challenges})
    snapshots = list(db.execute(text("""SELECT id FROM tasteduel.ranking_snapshots WHERE game_id=ANY(:games)
        OR expires_at<=clock_timestamp() ORDER BY id LIMIT 1000"""), {"games": games}).scalars())
    entities = list(db.execute(text("SELECT id FROM tasteduel.entities WHERE expires_at<=clock_timestamp() ORDER BY id LIMIT 1000")).scalars())
    parameters = {"owners": owners, "challenges": challenges, "games": games, "snapshots": snapshots, "entities": entities}
    exhausted = False
    for _ in range(3 if execute else 1):
        for table in tables:
            if time.monotonic()-started > 25:
                exhausted = True
                break  # Commit completed work; the next bounded run continues.
            candidates = ["t.id=ANY(:owners)"] if table.name == "sessions" else ["t.session_id=ANY(:owners)"]
            for column, parameter in (("game_id", "games"), ("snapshot_id", "snapshots"), ("challenge_id", "challenges"), ("entity_id", "entities")):
                if column in table.c:
                    candidates.append(f't."{column}"=ANY(:{parameter})')
            if "expires_at" in table.c:
                candidates.append("t.expires_at<=clock_timestamp()")
            if table.name == "challenges":
                # Only these bounded graph roots have had every affected
                # participant checked/revoked before their edges can vanish.
                candidates = ["t.id=ANY(:challenges)"]
            if table.name == "games":
                candidates = ["t.id=ANY(:games)"]
            if table.name == "usage_counters":
                candidates.append("t.window_end<=clock_timestamp()")
            predicate = "(" + " OR ".join(candidates) + f") AND tasteduel.maintenance_deletable('{table.name}',to_jsonb(t))"
            if execute:
                # Foreign-key references are checked before deletion; oversized batches
                # leave parents for the next run rather than cascading active rows.
                predicate += " AND " + _unreferenced(table)
                if table.name == "challenges":
                    predicate += " AND EXISTS(SELECT 1 FROM tasteduel.challenge_tombstones z WHERE z.slug_hash=t.slug_hash)"
                ordering = "t.id" if table.name == "sessions" else "t.session_id,t.id"
                result = db.execute(text(f'''DELETE FROM tasteduel."{table.name}" WHERE id IN
                    (SELECT t.id FROM tasteduel."{table.name}" t WHERE {predicate}
                     ORDER BY {ordering} LIMIT 100)'''), parameters)
                counts[table.name] = counts.get(table.name, 0)+result.rowcount
            else:
                counts[table.name] = db.execute(text(f'''SELECT count(*) FROM
                    (SELECT 1 FROM tasteduel."{table.name}" t WHERE {predicate} LIMIT 101) bounded'''), parameters).scalar_one()
        if exhausted:
            break
    if execute:
        counts["usage_budgets"] = db.execute(text("""DELETE FROM tasteduel.usage_budgets WHERE (scope_hash,bucket) IN
          (SELECT scope_hash,bucket FROM tasteduel.usage_budgets WHERE expires_at<=clock_timestamp()
           ORDER BY expires_at LIMIT 100)""")).rowcount
        counts["challenge_tombstones"] = db.execute(text("""DELETE FROM tasteduel.challenge_tombstones
            WHERE slug_hash IN(SELECT slug_hash FROM tasteduel.challenge_tombstones
              WHERE expires_at<=clock_timestamp() ORDER BY slug_hash LIMIT 100)""")).rowcount
    oldest = db.execute(text("""SELECT coalesce(max(extract(epoch FROM (clock_timestamp()-coalesce(revoked_at,
        tasteduel.session_deadline(id),expires_at)))) FILTER(WHERE NOT tasteduel.session_live(id)),0)
        FROM tasteduel.sessions WHERE id=ANY(:owners)"""), {"owners": owners}).scalar_one()
    return {"operation": "purge-expired", "executed": execute, "bounded_counts": counts,
            "oldest_expired_session_seconds": max(0, int(oldest)),
            "batch_deadline_reached": exhausted,
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


def verified_schema_revision(db):
    revision = db.execute(text("SELECT version_num FROM tasteduel.tasteduel_alembic_version")).scalar_one()
    if revision != "td0014":
        raise OperationBlocked("MIGRATION_REVISION_VERIFICATION_FAILED")
    return revision


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
            from tasteduel.adapters.database_secrets import resolve_database_url
            from tasteduel.config import Settings
            from tasteduel.persistence.db import database_engine

            settings = Settings()
            engine = database_engine(resolve_database_url(settings, migration=True), migration=True, mode=settings.database_mode)
            with engine.begin() as db:
                revision = verified_schema_revision(db)
            facts = {"operation": "migrate", "schema_revision": revision, "executed": True}
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
