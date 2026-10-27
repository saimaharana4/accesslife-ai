"""Synthetic, owned surface checks through the production BFF. No provider IO.

Cookies/pools stay in process memory; persist only aggregate evidence and the
authorized original-artwork OG image. Never inspect other guests' records.
"""

from datetime import UTC, datetime, timedelta
import importlib.util
import json
from pathlib import Path
import sys
from uuid import UUID, uuid4

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))
from tasteduel.api.main import create_app  # noqa: E402
from tasteduel.config import Settings  # noqa: E402
from tasteduel.persistence import models as m  # noqa: E402
from tasteduel.persistence.db import local_engine, scoped_session  # noqa: E402
from tasteduel.adapters.usage_budget import reserve  # noqa: E402


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    local = load("surface_local", ROOT / "scripts/tasteduel_local.py")
    if not local.verify_scope():
        raise RuntimeError("Recognized local database required")
    _, runtime = local.bootstrap()
    engine = local_engine(runtime)
    fixture = load("surface_fixture", ROOT / "tests/tasteduel/gameplay/conftest.py")
    curator = fixture.SyntheticCurator()
    origin = "http://127.0.0.1:3001"
    with TestClient(
        create_app(
            Settings(cookie_secure=False, allowed_origins=("https://testserver",)),
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
                    provider="fixture",
                    provider_entity_id=str(seed),
                    name='SYNTHETIC <img src=x onerror="P13_EXEC">',
                    attribution="Owned synthetic surface test",
                    rights_policy="project_owned",
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            )
        created = seed_client.post(
            "/v1/games",
            json={"seed_entity_id": str(seed), "seed_type": "artist"},
            headers={"Idempotency-Key": "synthetic-surface-create-0001"},
        )
        assert created.status_code == 201
        game = created.json()
    forbidden = {
        "chain_of_thought",
        "thought_signature",
        "private_pool",
        "raw_payload",
        "full_receipt",
        "affinity",
        "rank",
        "winner_entity_id",
    }

    def check_shape(value):
        if isinstance(value, dict):
            assert not forbidden.intersection(value)
            for child in value.values():
                check_shape(child)
        elif isinstance(value, list):
            for child in value:
                check_shape(child)

    out = ROOT / ".data/tasteduel-prompt13"
    with scoped_session(engine, owner) as db:
        names = set(
            db.scalars(select(m.Entity.name).where(m.Entity.session_id == owner, m.Entity.id != seed))
        )
    with httpx.Client(
        base_url=origin,
        trust_env=False,
        timeout=15,
        headers={"Origin": origin},
        cookies={"tasteduel_session": cookie},
    ) as browser:
        visible = set()
        game_id = game["game_id"]
        for ordinal in range(1, 6):
            current = browser.get(f"/api/v1/games/{game_id}").json()["current_round"]
            check_shape(current)
            assert "winning_choice_id" not in current and "curation_summary" not in current
            visible.update(c["entity"]["name"] for c in current["choices"])
            assert all(name not in json.dumps(current) for name in names - visible)
            if ordinal == 1:
                for headers in ({}, {"RSC": "1"}):
                    response = browser.get(f"/g/{game_id}", headers=headers)
                    assert "no-store" in response.headers.get("cache-control", "")
                    assert all(name not in response.text for name in names)
            answer = browser.post(
                f"/api/v1/games/{game_id}/answer",
                json={
                    "round_id": current["round_id"],
                    "choice_id": current["choices"][0]["id"],
                    "expected_revision": current["revision"],
                },
                headers={"Idempotency-Key": f"synthetic-surface-answer-{ordinal:04}"},
            )
            assert answer.status_code == 200
            reveal = answer.json()
            check_shape(reveal)
            assert all(name not in json.dumps(reveal) for name in names - visible)
            if ordinal < 5:
                assert reveal.get("curation_summary") is None
            assert (
                browser.post(
                    f"/api/v1/games/{game_id}/advance",
                    json={"answered_round_id": current["round_id"], "expected_revision": reveal["revision"]},
                    headers={"Idempotency-Key": f"synthetic-surface-advance-{ordinal:04}"},
                ).status_code
                == 200
            )
        share = browser.post(
            "/api/v1/challenges",
            json={"game_id": game_id},
            headers={"Idempotency-Key": "synthetic-surface-share-0001"},
        )
        assert share.status_code == 201
        slug = share.json()["invitation"]["slug"]
        with httpx.Client(base_url=origin, trust_env=False, timeout=15) as anonymous:
            invitation = anonymous.get(f"/api/v1/challenges/{slug}")
            assert invitation.status_code == 200
            check_shape(invitation.json())
            assert set(invitation.json()) == {
                "slug",
                "seed",
                "creator_score",
                "total",
                "source",
                "expires_at",
            }
            for headers in ({}, {"RSC": "1"}):
                response = anonymous.get(f"/c/{slug}", headers=headers)
                assert "no-store" in response.headers.get("cache-control", "")
                assert cookie not in response.text and str(owner) not in response.text
                assert "<img src=x onerror=" not in response.text
                assert all(name not in response.text for name in names)
            image = anonymous.get(f"/c/{slug}/social")
            assert image.status_code == 200 and image.content.startswith(b"\x89PNG\r\n\x1a\n")
            assert "no-store" in image.headers.get("cache-control", "")
            (out / "social-surface.png").write_bytes(image.content)
        # Exhaust only this synthetic guest's current mutation window. Clearing
        # remains available through the real BFF, including a lost-response retry.
        import hashlib

        scope = hashlib.sha256(f"guest-admission:{owner}".encode()).hexdigest()
        with engine.begin() as db:
            db.execute(text("SELECT set_config('app.usage_scope',:scope,true)"), {"scope": scope})
            # Keep this synthetic window active across the following HTTP proof,
            # avoiding a UTC minute boundary turning a throttle into a reset.
            db.execute(
                text(
                    "UPDATE tasteduel.usage_budgets SET window_start=clock_timestamp(), expires_at=clock_timestamp()+interval '60 seconds' WHERE scope_hash=:scope AND bucket='guest-mutation'"
                ),
                {"scope": scope},
            )
            used = db.execute(
                text(
                    "SELECT used FROM tasteduel.usage_budgets WHERE scope_hash=:scope AND bucket='guest-mutation'"
                ),
                {"scope": scope},
            ).scalar_one()
            reserve(db, scope, "guest-mutation", limit=120, seconds=60, amount=max(0, 120 - used))
        assert browser.post("/api/v1/sessions", json={}).status_code == 429
        assert browser.delete("/api/v1/sessions/current").status_code == 204
        assert (
            browser.delete(
                "/api/v1/sessions/current", headers={"Cookie": f"tasteduel_session={cookie}"}
            ).status_code
            == 204
        )
        renewed = browser.post("/api/v1/sessions", json={}, headers={"Cookie": f"tasteduel_session={cookie}"})
        assert renewed.status_code == 201 and renewed.json()["resumable_game_ids"] == []
        assert browser.delete("/api/v1/sessions/current").status_code == 204
    result = {
        "synthetic_only": True,
        "html_rsc_invitation_dto_checks": True,
        "preanswer_and_accepted_round_isolation": True,
        "malicious_title_escaped": True,
        "anonymous_og_original_artwork": True,
        "provider_calls": 0,
        "rate_limited_clear_and_stale_cookie_recovery": True,
        "log_secrecy_evidence": "separate unexpected-exception caplog contract in test_usage_budgets.py",
    }
    (out / "surface-verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    engine.dispose()
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"status": "failed", "safe_error_type": type(error).__name__}))
        raise SystemExit(1) from None
