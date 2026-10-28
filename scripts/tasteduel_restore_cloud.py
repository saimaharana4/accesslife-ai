"""Explicitly authorized, priced same-instance logical restore rehearsal.

Requires pinned cloud-sql-python-connector[psycopg]==1.23.0 locally. Nothing runs
on import. Pinned secrets/ADC stay in memory; private snapshot bytes are never
written to files. This does not prove managed Cloud SQL backup restore.
"""

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from uuid import UUID

from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


def main():
    sys.path.insert(0, str(ROOT / "apps/api/src"))
    import tasteduel_foundation_plan as planner
    from tasteduel.config import CLOUD_SQL_CONNECTION, SECRET_PREFIX, validate_database_url
    from tasteduel_restore import RestoreTarget, create_target, drop_target, exercise_restored_replay, export_sessions, restore_sessions, verify_restored

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-reviewed-restore", action="store_true")
    parser.add_argument("--cost", type=Path, required=True)
    parser.add_argument("--session", type=UUID, action="append", required=True)
    args = parser.parse_args()
    if not args.execute_reviewed_restore:
        parser.error("Restore mutation requires the explicitly reviewed execution flag.")
    target = RestoreTarget.fresh()
    result = {"started_at": datetime.now(UTC).isoformat(), "mode": "scoped-private-memory-logical-restore",
              "managed_backup_restore_proven": False, "source_database_modified": False,
              "backup_payload_files_written": False, "new_instance_created": False}
    stage = "cost"
    target_attempted = False
    connector = None
    try:
        planner.approved_variables(json.loads(args.cost.read_text(encoding="utf-8")))
        if not 1 <= len(args.session) <= 2 or len(set(args.session)) != len(args.session):
            raise RuntimeError("Expected one or two distinct validation sessions")
        from google.cloud import secretmanager
        from google.cloud.sql.connector import Connector, IPTypes

        stage = "credentials"
        with secretmanager.SecretManagerServiceClient() as client:
            def secret(name):
                return client.access_secret_version(request={"name": SECRET_PREFIX + name + "/versions/1"}, retry=None, timeout=5).payload.data.decode("utf-8")

            credentials = {"accesslife": secret("accesslife-db-password")}
            for actor, username in [("runtime", "tasteduel_runtime"), ("migrate", "tasteduel_migrator")]:
                value = secret(f"tasteduel-{actor}-database-url")
                validate_database_url(value, mode="cloud_sql", migration=actor == "migrate")
                credentials[username] = make_url(value).password
                del value
        connector = Connector(refresh_strategy="LAZY")

        def connect(user, database):
            if database not in {"tasteduel", target.name}:
                raise RuntimeError("Connection outside exact source/disposable target")
            return connector.connect(CLOUD_SQL_CONNECTION, "psycopg", user=user, password=credentials[user],
                                     db=database, ip_type=IPTypes.PUBLIC, timeout=15,
                                     options="-csearch_path=tasteduel,pg_catalog")

        def admin_factory(database):
            return connect("accesslife", database)

        def migrator_factory(database):
            return connect("tasteduel_migrator", database)

        def runtime_factory(database):
            return connect("tasteduel_runtime", database)
        stage = "source_snapshot"
        with runtime_factory("tasteduel") as source:
            backup = export_sessions(source, args.session)
        stage = "new_disposable_target"
        target_attempted = True
        result["disposable_target"] = target.name
        create_target(admin_factory, migrator_factory, target)
        stage = "logical_import"
        with migrator_factory(target.name) as owner:
            result.update(restore_sessions(owner, target, backup))
        stage = "restored_verification"
        with runtime_factory(target.name) as restored:
            result.update(verify_restored(restored, target, backup))
        stage = "actual_restored_replay"
        result.update(exercise_restored_replay(runtime_factory, target, args.session[0]))
        result.update(status="PASS", schema_revision=backup.revision, source_sessions=len(args.session),
                      table_session_counts_checked=len(backup.counts), private_backup_bytes=backup.byte_count)
        del backup
    except Exception as failure:
        result.update(status="BLOCKED", failed_stage=stage, failure_type=type(failure).__name__, sqlstate=getattr(failure, "sqlstate", None))
    finally:
        if target_attempted:
            try:
                result.update(drop_target(admin_factory, target))
            except Exception as failure:
                result.update(status="BLOCKED", cleanup_failed=True, cleanup_failure_type=type(failure).__name__)
        if connector is not None:
            connector.close()
        result["completed_at"] = datetime.now(UTC).isoformat()
    destination = ROOT / ".data/tasteduel-cloud-review/cloud-logical-restore.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
