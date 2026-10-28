"""Clean-schema/logical-restore acceptance in the labelled loopback test container.

Creates only a new local tasteduel source fixture and randomized disposable DB;
refuses either pre-existing source DB/admin role. Uses project-owned synthetic
games. This is not a cloud rehearsal or a live-provider product test.
"""

from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import secrets
import sys
from urllib.parse import quote
from uuid import UUID, uuid4

import psycopg
from psycopg import sql
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parents[1]


def main():
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "apps/api/src"))
    import tasteduel_local as local
    from tasteduel_database_foundation import bootstrap_staged
    from tasteduel_restore import RestoreTarget, create_target, drop_target, exercise_restored_replay, export_sessions, render_schema_sql, restore_sessions, verify_restored
    from tasteduel.api.main import create_app
    from tasteduel.config import Settings
    from tasteduel.persistence import models as m
    from tasteduel.persistence.db import scoped_session
    from fastapi.testclient import TestClient
    from tests.tasteduel.gameplay.conftest import SyntheticCurator
    from tests.tasteduel.gameplay.test_authoritative_flow import create, post
    from tests.tasteduel.gameplay.test_challenges import complete

    stage, engine = "scope", None
    created_source = created_role = created_target = False
    target = RestoreTarget.fresh()
    marker = "tasteduel-local-clean-lineage-" + secrets.token_hex(16)
    result = {"provider_calls": 0, "cloud_resources_changed": False,
              "dataset": "project-owned-synthetic", "credential_payload_files": False}
    try:
        if not local.verify_scope():
            raise RuntimeError("Expected labelled local container")
        admin_password, migrator_password, runtime_password = local.credentials()
        fixture_admin_password = secrets.token_urlsafe(40)

        def connect(user, password, database):
            return psycopg.connect(host="127.0.0.1", port=local.PORT, dbname=database,
                                   user=user, password=password, application_name="tasteduel-local-restore-test")

        def admin_factory(database):
            return connect("accesslife", fixture_admin_password, database)

        def migrator_factory(database):
            return connect("tasteduel_migrator", migrator_password, database)

        stage = "create_local_fixture"
        with connect("tasteduel_admin", admin_password, local.DATABASE) as root:
            if root.execute("SELECT 1 FROM pg_database WHERE datname='tasteduel'").fetchone() or root.execute("SELECT 1 FROM pg_roles WHERE rolname='accesslife'").fetchone():
                raise RuntimeError("Local fixture identity already exists; refusing adoption")
            root.rollback()
            root.autocommit = True
            root.execute(sql.SQL("CREATE ROLE accesslife LOGIN CREATEDB CREATEROLE PASSWORD {}").format(sql.Literal(fixture_admin_password)))
            created_role = True
            root.execute("GRANT tasteduel_runtime,tasteduel_migrator TO accesslife WITH ADMIN TRUE, INHERIT FALSE, SET FALSE")
            root.execute("CREATE DATABASE tasteduel OWNER accesslife")
            created_source = True
            root.execute(sql.SQL("COMMENT ON DATABASE tasteduel IS {}").format(sql.Literal(marker)))
        with admin_factory("tasteduel") as admin, migrator_factory("tasteduel") as migrator:
            bootstrap_staged(admin, migrator)
        stage = "clean_lineage"
        with migrator_factory("tasteduel") as owner:
            owner.execute(render_schema_sql())
            owner.commit()
        url = "postgresql+psycopg://tasteduel_runtime:" + quote(runtime_password, safe="") + "@127.0.0.1:" + str(local.PORT) + "/tasteduel"
        engine = create_engine(url, hide_parameters=True, connect_args={"options": "-csearch_path=tasteduel,pg_catalog"})
        stage = "synthetic_authoritative_sample"
        with TestClient(create_app(Settings(cookie_secure=True, allowed_origins=("https://testserver",)), engine=engine, generator=SyntheticCurator()),
                        base_url="https://testserver", headers={"Origin": "https://testserver"}) as client:
            if client.post("/v1/sessions", json={}).status_code != 201:
                raise RuntimeError("Synthetic session failed")
            session_id = UUID(client.cookies.get("tasteduel_session").split(".", 1)[0])
            seed = uuid4()
            with scoped_session(engine, session_id) as db:
                db.add(m.Entity(id=seed, session_id=session_id, entity_type="artist", name="Synthetic restore seed",
                                provider="fixture", provider_entity_id=str(seed), attribution="Project-owned validation data",
                                rights_policy="project_owned", expires_at=datetime.now(UTC) + timedelta(hours=1)))
            created = create(client, {"seed_entity_id": str(seed), "seed_type": "artist", "mode": "solo"})
            if created.status_code != 201:
                raise RuntimeError("Synthetic game creation failed")
            game = created.json()
            game, _ = complete(client, game)
            challenge = post(client, "/v1/challenges", {"game_id": game["game_id"]}, "local-restore-challenge-0001")
            if challenge.status_code != 201:
                raise RuntimeError("Synthetic challenge failed")
        stage = "private_memory_snapshot"
        with connect("tasteduel_runtime", runtime_password, "tasteduel") as runtime:
            backup = export_sessions(runtime, [session_id])
        stage = "disposable_schema"
        create_target(admin_factory, migrator_factory, target)
        created_target = True
        stage = "logical_restore"
        with migrator_factory(target.name) as owner:
            restore_sessions(owner, target, backup)
        stage = "restored_data_verification"
        with connect("tasteduel_runtime", runtime_password, target.name) as runtime:
            result.update(verify_restored(runtime, target, backup))
        stage = "restored_challenge_behavior"
        result.update(exercise_restored_replay(lambda database: connect("tasteduel_runtime", runtime_password, database), target, session_id))
        result.update(status="PASS", clean_lineage_revision=backup.revision, tables_checked=len(backup.counts),
                      private_backup_bytes=backup.byte_count, restored_five_round_replay=True)
        del backup
    except Exception as failure:
        result.update(status="BLOCKED", stage=stage, failure_type=type(failure).__name__, sqlstate=getattr(failure, "sqlstate", None))
        if stage == "clean_lineage":
            result["schema_error_position"] = getattr(getattr(failure, "diag", None), "statement_position", None)
    finally:
        if engine is not None:
            engine.dispose()
        try:
            if created_target:
                drop_target(admin_factory, target)
                result["disposable_target_removed"] = True
            if created_source or created_role:
                with connect("tasteduel_admin", admin_password, local.DATABASE) as root:
                    if created_source:
                        actual = root.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname='tasteduel'").fetchone()
                        root.rollback()
                        if actual != (marker,):
                            raise RuntimeError("Local source fixture marker mismatch")
                        root.autocommit = True
                        root.execute("DROP DATABASE tasteduel")
                    if created_role:
                        root.execute("DROP ROLE accesslife")
                result["local_source_fixture_removed"] = True
        except Exception as failure:
            result.update(status="BLOCKED", cleanup_failure_type=type(failure).__name__)
    output = ROOT / ".data/tasteduel-cloud-review/local-clean-lineage-restore.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))
    return 0 if result.get("status") == "PASS" else 2


if __name__ == "__main__":
    os.environ.pop("TASTEDUEL_DATABASE_MODE", None)
    raise SystemExit(main())
