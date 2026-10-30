"""Synthetic-only process-restart proof against the recognized local Taste Duel DB.

Creates a new guest/game. Never resets existing data, reads credential files or
calls providers. Container-derived local runtime credentials remain in memory.
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
import psycopg  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402
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
    local = load("prompt11_local_scope", ROOT / "scripts/tasteduel_local.py")
    if not local.verify_scope():
        raise RuntimeError("Recognized dedicated local database must already exist")
    # This helper validates loopback address, logical database and runtime role.
    _, runtime = local.bootstrap()
    engine = local_engine(runtime)
    fixture = load("prompt11_owned_fixture", ROOT / "quality/tasteduel/gameplay/conftest.py")
    curator = fixture.SyntheticCurator()
    with TestClient(
        create_app(
            Settings(cookie_secure=True, allowed_origins=("https://testserver",)),
            engine=engine,
            generator=curator,
        ),
        base_url="https://testserver",
        headers={"Origin": "https://testserver"},
    ) as seed_client:
        assert seed_client.post("/v1/sessions", json={}).status_code == 201
        cookie = seed_client.cookies.get("tasteduel_session")
        owner = UUID(cookie.split(".", 1)[0])
        seed = uuid4()
        with scoped_session(engine, owner) as db:
            db.add(
                m.Entity(
                    id=seed,
                    session_id=owner,
                    entity_type="artist",
                    name="SYNTHETIC Prompt 11 restart seed",
                    provider="fixture",
                    provider_entity_id=str(seed),
                    attribution="Project-owned synthetic test",
                    rights_policy="project_owned",
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            )
        created = seed_client.post(
            "/v1/games",
            json={"seed_entity_id": str(seed), "seed_type": "artist"},
            headers={"Idempotency-Key": "synthetic-prompt11-create"},
        )
        assert created.status_code == 201
        game_id = created.json()["game_id"]
    origin = "http://127.0.0.1:8003"
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "apps/api/src"),
        "TASTEDUEL_DATABASE_URL": runtime,
        "TASTEDUEL_QLOO_ENABLED": "false",
        "TASTEDUEL_GENERATION_ENABLED": "false",
        "TASTEDUEL_ALLOWED_ORIGINS": json.dumps([origin]),
        "TASTEDUEL_COOKIE_SECURE": "false",
    }
    process = None

    def stop():
        nonlocal process
        if process:
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
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("Owned API process exited")
            try:
                if httpx.get(origin + "/v1/health/ready", trust_env=False, timeout=1).status_code == 200:
                    return
            except httpx.TransportError:
                pass
            time.sleep(0.1)
        raise RuntimeError("Owned API did not become ready")

    # Refuse to adopt or terminate an existing listener.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 8003))
    try:
        start()
        with httpx.Client(
            base_url=origin,
            headers={"Origin": origin, "Cookie": "tasteduel_session=" + cookie},
            trust_env=False,
            timeout=10,
        ) as client:
            expected_score = 0
            seen = set()
            with scoped_session(engine, owner) as db:
                before = {
                    pair.id: (pair.winner_entity_id, pair.difficulty)
                    for pair in db.scalars(
                        select(m.PrivatePair).where(m.PrivatePair.game_id == UUID(game_id))
                    )
                }
            for ordinal, should_match in enumerate([True, True, False, True, False], 1):
                current = client.get(f"/v1/games/{game_id}").json()["current_round"]
                assert current["state"] == "unanswered" and current["ordinal"] == ordinal
                assert not {"winning_choice_id", "selected_choice_id", "affinity", "difficulty"}.intersection(
                    current
                )
                entities = {choice["entity"]["id"] for choice in current["choices"]}
                assert len(entities) == 2 and not entities.intersection(seen)
                seen.update(entities)
                with scoped_session(engine, owner) as db:
                    delivered = db.get(m.DeliveredRound, UUID(current["round_id"]))
                    winner = db.get(m.PrivatePair, delivered.pair_id).winner_entity_id
                selected = next(
                    c for c in current["choices"] if (UUID(c["entity"]["id"]) == winner) == should_match
                )
                answer_body = {
                    "round_id": current["round_id"],
                    "choice_id": selected["id"],
                    "expected_revision": current["revision"],
                }
                answer_key = {"Idempotency-Key": f"synthetic-prompt11-answer-{ordinal}"}
                accepted = client.post(f"/v1/games/{game_id}/answer", json=answer_body, headers=answer_key)
                assert accepted.status_code == 200 and accepted.json()["correct"] == should_match
                reveal = accepted.json()
                # The client could lose this response after commit. Restart before recovery.
                if ordinal in (1, 3):
                    stop()
                    start()
                restored = client.get(f"/v1/games/{game_id}").json()["current_round"]
                assert restored == reveal
                repeated = client.post(f"/v1/games/{game_id}/answer", json=answer_body, headers=answer_key)
                assert repeated.status_code == 200 and repeated.json() == reveal
                expected_score += int(should_match)
                assert reveal["cumulative_score"] == expected_score
                discoveries = client.get("/v1/discoveries")
                assert discoveries.status_code == 200
                assert len(discoveries.json()["discoveries"]) == (1 if ordinal > 1 else 0), (
                    "Predictions cannot create saved preferences"
                )
                if ordinal == 1:
                    save = client.post(
                        "/v1/discoveries",
                        json={"entity_id": selected["entity"]["id"]},
                        headers={"Idempotency-Key": "synthetic-discovery-save"},
                    )
                    assert save.status_code in (200, 201)
                    stop()
                    start()
                    assert len(client.get("/v1/discoveries").json()["discoveries"]) == 1
                advance_body = {
                    "answered_round_id": reveal["round_id"],
                    "expected_revision": reveal["revision"],
                }
                advance_key = {"Idempotency-Key": f"synthetic-prompt11-next-{ordinal}"}
                advanced = client.post(f"/v1/games/{game_id}/advance", json=advance_body, headers=advance_key)
                assert advanced.status_code == 200
                if ordinal in (2, 4):
                    stop()
                    start()
                saved_game = client.get(f"/v1/games/{game_id}").json()
                assert saved_game == advanced.json()
                repeated_next = client.post(
                    f"/v1/games/{game_id}/advance", json=advance_body, headers=advance_key
                )
                assert repeated_next.status_code == 200 and repeated_next.json() == advanced.json()
            result = client.get(f"/v1/games/{game_id}/results").json()
            assert result["score"] == expected_score == 3 and len(result["answered_rounds"]) == 5
            assert len(result["discoveries"]) == 1
            with scoped_session(engine, owner) as db:
                after = {
                    pair.id: (pair.winner_entity_id, pair.difficulty)
                    for pair in db.scalars(
                        select(m.PrivatePair).where(m.PrivatePair.game_id == UUID(game_id))
                    )
                }
            assert before == after
            assert client.delete("/v1/sessions/current").status_code == 204
            assert client.get(f"/v1/games/{game_id}").status_code == 401
            assert client.get("/v1/discoveries").status_code == 401
            # Session revocation does not rewrite historic correctness.
            # The runtime role must see no revoked-session data under forced RLS.
            with scoped_session(engine, owner) as db:
                assert list(db.scalars(select(m.Answer).where(m.Answer.game_id == UUID(game_id)))) == []
            # A separate local-only read-only administrative audit verifies rows
            # remain stored; do not weaken RLS or reopen the session to inspect.
            admin, _, _ = local.credentials()
            with psycopg.connect(
                host="127.0.0.1",
                port=55435,
                dbname="tasteduel_local",
                user="tasteduel_admin",
                password=admin,
            ) as audit:
                audit.execute("SET TRANSACTION READ ONLY")
                count, score = audit.execute(
                    "SELECT count(*), sum(correct::integer) FROM tasteduel.answers WHERE game_id=%s",
                    (UUID(game_id),),
                ).fetchone()
                assert count == 5 and score == 3
        assert curator.calls == 1
        report = {
            "synthetic_only": True,
            "five_rounds": True,
            "answer_restart_recoveries": 2,
            "advance_restart_recoveries": 2,
            "save_restart_recoveries": 1,
            "accepted_retry_score_stable": True,
            "no_repeat_contestants": len(seen) == 10,
            "private_winners_unchanged": before == after,
            "prediction_does_not_auto_save": True,
            "session_revoked": True,
            "historic_answers_preserved": True,
            "external_provider_calls": 0,
            "existing_local_database_retained": True,
        }
        out = ROOT / ".data/tasteduel-solo"
        out.mkdir(parents=True, exist_ok=True)
        (out / "process-recovery.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report))
    finally:
        stop()
        engine.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception as failure:
        trace = failure.__traceback__
        locations = []
        while trace:
            locations.append({"file": Path(trace.tb_frame.f_code.co_filename).name, "line": trace.tb_lineno})
            trace = trace.tb_next
        print(
            json.dumps(
                {
                    "status": "failed",
                    "safe_error_type": type(failure).__name__,
                    "locations": locations,
                    "no_data_reset": True,
                }
            ),
            file=sys.stderr,
        )
        raise SystemExit(1)
