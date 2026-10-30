"""Exercise td0011 data through the actual nickname migration in isolated CI.

Requires the dedicated empty loopback test database, never discovers cloud or
legacy configuration. Legacy synthetic API fixtures produce the committed graph.
"""

import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "99c23fc8824e8588af4e4c794e7683607e18e53c"
sys.path.insert(0, str(ROOT / "apps/api/src"))
from tasteduel.config import validate_local_url  # noqa: E402


def alembic(environment, revision):
    subprocess.run([sys.executable, "-m", "alembic", "-c", "apps/api/tasteduel-alembic.ini",
                    "upgrade", revision], cwd=ROOT, env=environment, check=True,
                   capture_output=True, text=True)


def guards(db):
    return (tuple(db.execute(text("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='tasteduel.challenge_plays'::regclass")).one()) == (True, True)
            and db.execute(text("SELECT tgenabled FROM pg_trigger WHERE tgrelid='tasteduel.challenge_plays'::regclass AND tgname='immutable_record'")).scalar_one() == "O"
            and db.execute(text("SELECT count(*) FROM pg_policy WHERE polrelid='tasteduel.challenge_plays'::regclass AND polname='migration_attempt_backfill'")).scalar_one() == 0)


def main():
    owner = os.environ["TASTEDUEL_TEST_MIGRATION_DATABASE_URL"]
    runtime = os.environ["TASTEDUEL_TEST_DATABASE_URL"]
    validate_local_url(owner, migration=True)
    validate_local_url(runtime)
    environment = {**os.environ, "TASTEDUEL_MIGRATION_DATABASE_URL": owner,
                   "PYTHONPATH": str(ROOT / "apps/api/src"),
                   "TASTEDUEL_QLOO_ENABLED": "false", "TASTEDUEL_GENERATION_ENABLED": "false"}
    engine = create_engine(owner, hide_parameters=True)
    with engine.connect() as db:
        if db.execute(text("SELECT to_regclass('tasteduel.tasteduel_alembic_version')")).scalar_one() is not None:
            raise RuntimeError("A fresh dedicated migration-check database is required")
    alembic(environment, "td0011")
    archive = subprocess.run(["git", "archive", "--format=tar", BASELINE], cwd=ROOT,
                             capture_output=True, check=True).stdout
    with tempfile.TemporaryDirectory(prefix="tasteduel-upgrade-fixtures-") as scratch:
        source = Path(scratch)
        with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
            bundle.extractall(source, filter="data")
        # These are real legacy API mutations using project-owned synthetic
        # generation. Two distinct pre-upgrade attempts exercise ordinal grouping.
        seed = source / "quality/tasteduel/gameplay/test_upgrade_seed.py"
        seed.write_text('''from .test_challenges import shared
from .test_authoritative_flow import post

def test_seed_legacy_attempts(gameplay, owned_seed):
    _, _, _, _, _, share = shared(gameplay, owned_seed)
    guest, _, _ = gameplay()
    path = f"/v1/challenges/{share['invitation']['slug']}/plays"
    first = post(guest, path, {}, "upgrade-legacy-attempt-0001")
    second = post(guest, path, {}, "upgrade-legacy-attempt-0002")
    assert first.status_code == second.status_code == 201
    assert first.json()["game_id"] != second.json()["game_id"]
''', encoding="utf-8")
        legacy_environment = {**environment, "PYTHONPATH": str(source / "apps/api/src")}
        subprocess.run([sys.executable, "-m", "pytest", "-c", "pytest.tasteduel.ini",
                        "--confcutdir=quality/tasteduel", "quality/tasteduel/gameplay/test_upgrade_seed.py", "-q"],
                       cwd=source, env=legacy_environment, check=True, capture_output=True, text=True)
    with engine.connect() as db:
        original = db.execute(text("SELECT id,challenge_id,session_id,game_id,created_at FROM tasteduel.challenge_plays ORDER BY challenge_id,session_id,created_at,id")).all()
        assert len(original) == 2 and guards(db)
    # Inject failure after opening the narrowly scoped backfill. PostgreSQL must
    # roll back the column, policy and trigger change together.
    spec = importlib.util.spec_from_file_location("upgrade_under_test", ROOT / "apps/api/tasteduel_migrations/versions/0012_named_duels.py")
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    statements = []
    class Capture:
        @staticmethod
        def execute(sql):
            statements.append(sql)
    migration.op = Capture
    migration.upgrade()
    assert len(statements) == 1
    broken = statements[0].replace("    WITH numbered AS", "    SELECT 1/0;\n    WITH numbered AS", 1)
    assert broken != statements[0]
    try:
        with engine.begin() as db:
            db.execute(text(broken))
        raise AssertionError("Injected migration failure did not fail")
    except DBAPIError:
        pass
    with engine.connect() as db:
        assert guards(db)
        assert db.execute(text("SELECT count(*) FROM information_schema.columns WHERE table_schema='tasteduel' AND table_name='challenge_plays' AND column_name='attempt_number'")).scalar_one() == 0
        assert db.execute(text("SELECT version_num FROM tasteduel.tasteduel_alembic_version")).scalar_one() == "td0011"
    alembic(environment, "head")
    with engine.connect() as db:
        upgraded = db.execute(text("SELECT id,challenge_id,session_id,game_id,created_at,attempt_number FROM tasteduel.challenge_plays ORDER BY challenge_id,session_id,created_at,id")).all()
        assert [tuple(row[:5]) for row in upgraded] == [tuple(row) for row in original]
        assert [row.attempt_number for row in upgraded] == [1, 2]
        assert guards(db)
        assert db.execute(text("SELECT version_num FROM tasteduel.tasteduel_alembic_version")).scalar_one() == "td0014"
    runtime_engine = create_engine(runtime, hide_parameters=True)
    try:
        with runtime_engine.begin() as db:
            db.execute(text("SELECT set_config('app.session_id',:owner,true)"), {"owner": str(original[0].session_id)})
            db.execute(text("UPDATE tasteduel.challenge_plays SET attempt_number=99 WHERE id=:id"), {"id": original[0].id})
        raise AssertionError("Runtime mutated immutable replay history")
    except DBAPIError:
        pass
    finally:
        runtime_engine.dispose()
    with engine.connect() as db:
        assert db.execute(text("SELECT attempt_number FROM tasteduel.challenge_plays ORDER BY attempt_number")).scalars().all() == [1, 2]
    engine.dispose()
    print(json.dumps({"status": "PASS", "from": "td0011", "to": "td0014",
                      "existing_attempts": 2, "rollback_restores_guards": True,
                      "runtime_immutability_preserved": True, "provider_calls": 0}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"status": "FAIL", "reason_code": "ISOLATED_NAMED_UPGRADE_VERIFICATION_FAILED"}))
        raise SystemExit(1) from None
