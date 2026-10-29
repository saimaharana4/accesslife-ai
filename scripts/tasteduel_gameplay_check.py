"""Clean local migration/gameplay check; no providers, cloud or data deletion.

Temporarily pauses the verified existing local DB, uses a separately labelled
new PostgreSQL container at the same guarded loopback address, then restores the
original container. Both databases remain intact. Refuses an existing check DB.
"""

import argparse
from datetime import UTC, datetime, timedelta
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text, select  # noqa: E402
from tasteduel.api.main import create_app  # noqa: E402
from tasteduel.config import Settings  # noqa: E402
from tasteduel.persistence import models as m  # noqa: E402
from tasteduel.persistence.db import local_engine, scoped_session  # noqa: E402


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def process_journey(runtime_url):
    engine = local_engine(runtime_url)
    fixture = load("owned_gameplay_fixture", ROOT / "tests/tasteduel/gameplay/conftest.py")
    curator = fixture.SyntheticCurator()
    with TestClient(
        create_app(
            Settings(cookie_secure=True, allowed_origins=("https://testserver",)),
            engine=engine,
            generator=curator,
        ),
        base_url="https://testserver",
        headers={"Origin": "https://testserver"},
    ) as client:
        assert client.post("/v1/sessions", json={}).status_code == 201
        token = client.cookies.get("tasteduel_session")
        owner = UUID(token.split(".")[0])
        seed = uuid4()
        with scoped_session(engine, owner) as db:
            db.add(
                m.Entity(
                    id=seed,
                    session_id=owner,
                    entity_type="artist",
                    name="SYNTHETIC restart seed",
                    provider="fixture",
                    provider_entity_id=str(seed),
                    attribution="Project-owned test data",
                    rights_policy="project_owned",
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            )
        created = client.post(
            "/v1/games",
            json={"seed_entity_id": str(seed), "seed_type": "artist"},
            headers={"Idempotency-Key": "synthetic-process-create"},
        )
        assert created.status_code == 201
        game_id = created.json()["game_id"]
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "apps/api/src"),
        "TASTEDUEL_DATABASE_URL": runtime_url,
        "TASTEDUEL_QLOO_ENABLED": "false",
        "TASTEDUEL_GENERATION_ENABLED": "false",
        "TASTEDUEL_ALLOWED_ORIGINS": '["http://127.0.0.1:8003"]',
        "TASTEDUEL_COOKIE_SECURE": "false",
    }
    origin = "http://127.0.0.1:8003"
    process = None

    def stop():
        nonlocal process
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            process = None

    def start():
        nonlocal process
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "tasteduel.api.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8003",
                "--no-access-log",
            ],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("Local API process exited")
            try:
                if httpx.get(origin + "/v1/health/ready", timeout=1, trust_env=False).status_code == 200:
                    return
            except httpx.TransportError:
                pass
            time.sleep(0.1)
        raise RuntimeError("Local API process did not become ready")

    # Refuse to mistake an unrelated listener for our child.
    import socket

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 8003))
    try:
        start()
        with httpx.Client(
            base_url=origin,
            headers={"Origin": origin, "Cookie": "tasteduel_session=" + token},
            trust_env=False,
            timeout=10,
        ) as client:
            expected_score = 0
            before_receipt = None
            with scoped_session(engine, owner) as db:
                before_receipt = db.scalar(
                    select(m.CurationReceipt.full_receipt).where(m.CurationReceipt.game_id == UUID(game_id))
                )
            for ordinal in range(1, 6):
                current = client.get(f"/v1/games/{game_id}").json()["current_round"]
                assert current["state"] == "unanswered" and current["ordinal"] == ordinal
                answer = client.post(
                    f"/v1/games/{game_id}/answer",
                    json={
                        "round_id": current["round_id"],
                        "choice_id": current["choices"][0]["id"],
                        "expected_revision": current["revision"],
                    },
                    headers={"Idempotency-Key": f"synthetic-process-answer-{ordinal}"},
                )
                assert answer.status_code == 200
                reveal = answer.json()
                expected_score += int(reveal["correct"])
                advance = client.post(
                    f"/v1/games/{game_id}/advance",
                    json={"answered_round_id": reveal["round_id"], "expected_revision": reveal["revision"]},
                    headers={"Idempotency-Key": f"synthetic-process-next-{ordinal}"},
                )
                assert advance.status_code == 200
                if ordinal == 2:
                    before = client.get(f"/v1/games/{game_id}").json()
                    stop()
                    start()
                    assert client.get(f"/v1/games/{game_id}").json() == before
            result = client.get(f"/v1/games/{game_id}/results")
            assert result.status_code == 200 and result.json()["score"] == expected_score
            assert result.json()["source"] == "fixture"
            with scoped_session(engine, owner) as db:
                assert (
                    db.scalar(
                        select(m.CurationReceipt.full_receipt).where(
                            m.CurationReceipt.game_id == UUID(game_id)
                        )
                    )
                    == before_receipt
                )
            assert curator.calls == 1
        with httpx.Client(base_url=origin, headers={"Origin": origin}, trust_env=False) as other:
            assert other.post("/v1/sessions", json={}).status_code == 201
            assert other.get(f"/v1/games/{game_id}").status_code == 404
        return {
            "api_process_restart": True,
            "full_five_round_game": True,
            "receipt_unchanged": True,
            "other_guest_denied": True,
            "fixture_mode": True,
            "external_provider_calls": 0,
        }
    finally:
        stop()
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean", action="store_true", required=True)
    parser.parse_args()
    os.chdir(ROOT)
    original = load("original_local_setup", ROOT / "scripts/tasteduel_local.py")
    clean = load("clean_local_setup", ROOT / "scripts/tasteduel_local.py")
    clean.CONTAINER = "tasteduel-gameplay-clean-db"
    clean.SCOPE = "tasteduel-gameplay-clean"
    if clean.docker("ps", "-a", "--filter", f"name=^/{clean.CONTAINER}$", "--format", "{{.Names}}"):
        raise RuntimeError("Clean check container already exists; retain it, do not reset its data")
    if not original.verify_scope():
        raise RuntimeError("The original dedicated local database must be recognised first")
    was_running = original.docker("inspect", "--format", "{{.State.Running}}", original.CONTAINER) == "true"
    report = {
        "original_preserved": True,
        "database": "tasteduel_local",
        "port": 55435,
        "clean_container": clean.CONTAINER,
        "cloud_changes": False,
        "credential_files_written": False,
    }
    out = ROOT / ".data/tasteduel-gameplay"
    out.mkdir(parents=True, exist_ok=True)
    try:
        if was_running:
            original.docker("stop", original.CONTAINER)
        clean.start()
        owner, runtime = clean.bootstrap()
        engine = local_engine(owner, migration=True)
        with engine.connect() as db:
            report["initial_application_tables"] = db.execute(
                text("SELECT count(*) FROM information_schema.tables WHERE table_schema='tasteduel'")
            ).scalar_one()
        engine.dispose()
        assert report["initial_application_tables"] == 0
        env = {
            **os.environ,
            "PYTHONPATH": str(ROOT / "apps/api/src"),
            "TASTEDUEL_MIGRATION_DATABASE_URL": owner,
            "TASTEDUEL_TEST_MIGRATION_DATABASE_URL": owner,
            "TASTEDUEL_TEST_DATABASE_URL": runtime,
        }
        subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "apps/api/tasteduel-alembic.ini", "upgrade", "head"],
            env=env,
            check=True,
        )
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-c",
                "pytest.tasteduel.ini",
                "--confcutdir=tests/tasteduel",
                "tests/tasteduel",
                "-q",
                "--junitxml=.data/tasteduel-gameplay/clean-tests.xml",
            ],
            env=env,
            check=True,
        )
        report.update(process_journey(runtime))
        report["migrations"] = "td0001 through td0006"
        (out / "clean-runtime.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report))
    finally:
        if clean.verify_scope():
            clean.docker("stop", clean.CONTAINER)
        if was_running:
            original.docker("start", original.CONTAINER)


if __name__ == "__main__":
    try:
        main()
    except Exception as failure:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "safe_error_type": type(failure).__name__,
                    "database_data_deleted": False,
                }
            ),
            file=sys.stderr,
        )
        raise SystemExit(1)
