"""Run real same-origin browser/API restart checks with newly-owned synthetic data.

The Python/Node handoff uses an anonymous synthetic test cookie in stdin only.
No provider, secret manager, cloud deployment, storageState or database reset.
"""

from datetime import UTC, datetime, timedelta
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from tasteduel.api.main import create_app  # noqa: E402
from tasteduel.config import Settings  # noqa: E402
from tasteduel.persistence import models as m  # noqa: E402
from tasteduel.persistence.db import local_engine, scoped_session  # noqa: E402


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    # Never adopt or stop an unrelated listener.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 8004))
    local = load("prompt11_browser_scope", ROOT / "scripts/tasteduel_local.py")
    if not local.verify_scope():
        raise RuntimeError("Only recognized local Taste Duel database is permitted")
    _, runtime = local.bootstrap()
    engine = local_engine(runtime)
    fixture = load("prompt11_browser_fixture", ROOT / "quality/tasteduel/gameplay/conftest.py")
    with TestClient(
        create_app(
            Settings(cookie_secure=True, allowed_origins=("https://testserver",)),
            engine=engine,
            generator=fixture.SyntheticCurator(),
        ),
        base_url="https://testserver",
        headers={"Origin": "https://testserver"},
    ) as client:
        assert client.post("/v1/sessions", json={}).status_code == 201
        cookie = client.cookies.get("tasteduel_session")
        owner = UUID(cookie.split(".", 1)[0])
        seed = uuid4()
        with scoped_session(engine, owner) as db:
            db.add(
                m.Entity(
                    id=seed,
                    session_id=owner,
                    entity_type="artist",
                    name="SYNTHETIC browser restart seed",
                    provider="fixture",
                    provider_entity_id=str(seed),
                    attribution="Project-owned synthetic browser check",
                    rights_policy="project_owned",
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            )
        created = client.post(
            "/v1/games",
            json={"seed_entity_id": str(seed), "seed_type": "artist"},
            headers={"Idempotency-Key": "synthetic-prompt11-browser-create"},
        )
        assert created.status_code == 201
        game_id = created.json()["game_id"]
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "apps/api/src"),
        "TASTEDUEL_DATABASE_URL": runtime,
        "TASTEDUEL_QLOO_ENABLED": "false",
        "TASTEDUEL_GENERATION_ENABLED": "false",
        "TASTEDUEL_ALLOWED_ORIGINS": '["http://127.0.0.1:3003"]',
        "TASTEDUEL_COOKIE_SECURE": "false",
    }
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "tasteduel.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8004",
            "--no-access-log",
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("Owned browser-check API exited")
            try:
                if (
                    httpx.get("http://127.0.0.1:8004/v1/health/ready", timeout=1, trust_env=False).status_code
                    == 200
                ):
                    break
            except httpx.TransportError:
                pass
            time.sleep(0.1)
        else:
            raise RuntimeError("Owned browser-check API not ready")
        result = subprocess.run(
            ["node", "scripts/tasteduel_solo_browser_restart.mjs"],
            input=json.dumps({"cookie": cookie, "game_id": game_id}),
            text=True,
            capture_output=True,
            cwd=ROOT,
            timeout=120,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        # The controlled Node helper emits only a redacted audit result. Never
        # forward arbitrary browser stderr, which may include diagnostics.
        value = json.loads(result.stdout.strip().splitlines()[-1])
        print(json.dumps(value))
        if result.returncode:
            raise RuntimeError("Browser restart gate failed")
    finally:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as failure:
        print(
            json.dumps(
                {"status": "failed", "safe_error_type": type(failure).__name__, "no_data_reset": True}
            ),
            file=sys.stderr,
        )
        raise SystemExit(1)
