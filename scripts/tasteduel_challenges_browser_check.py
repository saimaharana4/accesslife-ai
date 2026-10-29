"""New synthetic guests, real local API/BFF, two fixed browser replays.

No provider or cloud access. Session cookie travels through child stdin only;
neither cookies nor database credentials are written to evidence artifacts.
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
    origin = os.environ.get("TASTEDUEL_TEST_WEB_URL", "http://127.0.0.1:3003")
    if origin not in {"http://127.0.0.1:3001", "http://127.0.0.1:3003"}:
        raise RuntimeError("Only the two explicit loopback web previews are permitted")
    api_port = 8004 if origin.endswith(":3001") else 8005
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", api_port))
    local = load("prompt12_browser_scope", ROOT / "scripts/tasteduel_local.py")
    if not local.verify_scope():
        raise RuntimeError("Only the recognized local Taste Duel database is permitted")
    _, runtime = local.bootstrap()
    engine = local_engine(runtime)
    fixture = load("prompt12_fixture", ROOT / "tests/tasteduel/gameplay/conftest.py")
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
        assert client.post("/v1/sessions", json={"display_name": "Synthetic challenger"}).status_code == 201
        cookie = client.cookies.get("tasteduel_session")
        owner = UUID(cookie.split(".", 1)[0])
        seed = uuid4()
        with scoped_session(engine, owner) as db:
            db.add(
                m.Entity(
                    id=seed,
                    session_id=owner,
                    entity_type="artist",
                    name="SYNTHETIC Beyoncé 東京 — A Very Long Favourite for an Unexpected Cultural Fight Night",
                    provider="fixture",
                    provider_entity_id=str(seed),
                    attribution="Project-owned synthetic exact-replay test",
                    rights_policy="project_owned",
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            )
        created = client.post(
            "/v1/games",
            json={"seed_entity_id": str(seed), "seed_type": "artist"},
            headers={"Idempotency-Key": "synthetic-prompt12-browser-create"},
        )
        assert created.status_code == 201
        game_id = created.json()["game_id"]
        for ordinal, correct in enumerate([True, True, False, True, False], 1):
            current = client.get(f"/v1/games/{game_id}").json()["current_round"]
            with scoped_session(engine, owner) as db:
                delivered = db.get(m.DeliveredRound, UUID(current["round_id"]))
                winner = db.get(m.PrivatePair, delivered.pair_id).winner_entity_id
            choice = next(c for c in current["choices"] if (UUID(c["entity"]["id"]) == winner) == correct)
            answer = client.post(
                f"/v1/games/{game_id}/answer",
                json={
                    "round_id": current["round_id"],
                    "choice_id": choice["id"],
                    "expected_revision": current["revision"],
                },
                headers={"Idempotency-Key": f"synthetic-prompt12-answer-{ordinal}"},
            )
            assert answer.status_code == 200
            advance = client.post(
                f"/v1/games/{game_id}/advance",
                json={
                    "answered_round_id": current["round_id"],
                    "expected_revision": answer.json()["revision"],
                },
                headers={"Idempotency-Key": f"synthetic-prompt12-advance-{ordinal}"},
            )
            assert advance.status_code == 200
        assert client.get(f"/v1/games/{game_id}/results").json()["score"] == 3
        assert curator.calls == 1
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "apps/api/src"),
        "TASTEDUEL_DATABASE_URL": runtime,
        "TASTEDUEL_QLOO_ENABLED": "false",
        "TASTEDUEL_GENERATION_ENABLED": "false",
        "TASTEDUEL_ALLOWED_ORIGINS": json.dumps([origin]),
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
            str(api_port),
            "--no-access-log",
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("Owned browser-check API exited")
            try:
                if (
                    httpx.get(f"http://127.0.0.1:{api_port}/v1/health/ready", timeout=1, trust_env=False).status_code
                    == 200
                ):
                    break
            except httpx.TransportError:
                pass
            time.sleep(0.1)
        else:
            raise RuntimeError("Owned browser-check API not ready")
        result = subprocess.run(
            ["node", "scripts/tasteduel_challenges_browser_check.mjs"],
            input=json.dumps({"cookie": cookie, "game_id": game_id}),
            text=True,
            capture_output=True,
            cwd=ROOT,
            timeout=300,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        value = json.loads(result.stdout.strip().splitlines()[-1])
        print(json.dumps(value))
        if result.returncode:
            raise RuntimeError("Two-session browser replay gate failed")
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
