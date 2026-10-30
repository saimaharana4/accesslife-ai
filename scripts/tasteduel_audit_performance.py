"""Provider-free lab against production web3001 and provider-disabled API8005.

Creates newly scoped synthetic guests, never resets old data. ``--quick`` checks
the final build with two cold navigations and one pressed-feedback sample; its
separate artifact explicitly reuses the prior full API benchmark.
"""

from datetime import UTC, datetime, timedelta
import importlib.util
import json
from pathlib import Path
import statistics
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
    quick = "--quick" in sys.argv[1:]
    previous = None
    if quick:
        previous = json.loads(
            (ROOT / ".data/tasteduel-audit/performance.json").read_text(encoding="utf-8")
        )
    build_id = (ROOT / "apps/web/.next/BUILD_ID").read_text(encoding="utf-8").strip()
    ready = httpx.get("http://127.0.0.1:8005/v1/health/ready", timeout=5, trust_env=False)
    if ready.status_code != 200 or ready.json().get("generation_available") is not False:
        raise RuntimeError("A ready provider-disabled local API8005 is required")
    local = load("prompt13_local", ROOT / "scripts/tasteduel_local.py")
    if not local.verify_scope():
        raise RuntimeError("Dedicated local Taste Duel database required")
    _, runtime = local.bootstrap()
    engine = local_engine(runtime)
    fixture = load("prompt13_fixture", ROOT / "quality/tasteduel/gameplay/conftest.py")
    curator = fixture.SyntheticCurator()
    durations = []
    with TestClient(
        create_app(
            Settings(cookie_secure=False, allowed_origins=("http://127.0.0.1:3001",)),
            engine=engine,
            generator=curator,
        ),
        base_url="http://127.0.0.1:3001",
        headers={"Origin": "http://127.0.0.1:3001"},
    ) as setup:
        games = []
        for index in range(1 if quick else 8):
            setup.cookies.clear()
            assert setup.post("/v1/sessions", json={}).status_code == 201
            cookie = setup.cookies.get("tasteduel_session")
            owner = UUID(cookie.split(".", 1)[0])
            seed = uuid4()
            with scoped_session(engine, owner) as db:
                db.add(
                    m.Entity(
                        id=seed,
                        session_id=owner,
                        entity_type="artist",
                        name="SYNTHETIC performance favourite",
                        provider="fixture",
                        provider_entity_id=str(seed),
                        attribution="Project-owned lab fixture",
                        rights_policy="project_owned",
                        expires_at=datetime.now(UTC) + timedelta(hours=1),
                    )
                )
            created = setup.post(
                "/v1/games",
                json={"seed_entity_id": str(seed), "seed_type": "artist"},
                headers={"Idempotency-Key": f"prompt13-performance-lab-{index}"},
            )
            assert created.status_code == 201
            games.append({"cookie": cookie, "game_id": created.json()["game_id"]})
        # Real HTTP/private API handler + PostgreSQL; exclude TLS, BFF and providers.
        for index, game in enumerate([] if quick else games[:7]):
            with httpx.Client(
                base_url="http://127.0.0.1:8005",
                trust_env=False,
                timeout=10,
                headers={"Origin": "http://127.0.0.1:3001"},
                cookies={"tasteduel_session": game["cookie"]},
            ) as client:
                for ordinal in range(5):
                    current = client.get(f"/v1/games/{game['game_id']}").json()["current_round"]
                    before = time.perf_counter()
                    answered = client.post(
                        f"/v1/games/{game['game_id']}/answer",
                        json={
                            "round_id": current["round_id"],
                            "choice_id": current["choices"][0]["id"],
                            "expected_revision": current["revision"],
                        },
                        headers={"Idempotency-Key": f"prompt13-lab-answer-{ordinal}"},
                    )
                    elapsed = (time.perf_counter() - before) * 1000
                    assert answered.status_code == 200, answered.status_code
                    if index > 0:
                        durations.append(elapsed)
                    advanced = client.post(
                        f"/v1/games/{game['game_id']}/advance",
                        json={
                            "answered_round_id": current["round_id"],
                            "expected_revision": answered.json()["revision"],
                        },
                        headers={"Idempotency-Key": f"prompt13-lab-advance-{ordinal}"},
                    )
                    assert advanced.status_code == 200
        result = subprocess.run(
            ["node", "scripts/tasteduel_audit_performance.mjs"],
            input=json.dumps({**games[-1], "quick": quick}),
            text=True,
            capture_output=True,
            cwd=ROOT,
            timeout=300,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode:
            raise RuntimeError(
                "Browser performance lab failed; sanitized child result only: " + result.stdout[-1000:]
            )
        browser = json.loads(result.stdout.strip().splitlines()[-1])
    if quick:
        durations = previous["api"]["samples_ms"]
    targets = {
        "lcp_all_samples_at_most_2500_ms": all(row["lcp_ms"] <= 2500 for row in browser["samples"]),
        "cls_all_samples_at_most_0_1": all(row["cls"] <= 0.1 for row in browser["samples"]),
        "initial_js_at_most_180000_gzip_bytes": browser["javascript"]["initial_landing_gzip_bytes"]
        <= 180_000,
        "gameplay_addition_at_most_100000_gzip_bytes": browser["javascript"]["gameplay_addition_gzip_bytes"]
        <= 100_000,
        "pressed_feedback_all_below_100_ms": max(browser["immediate_pressed_feedback_ms"]) < 100,
        "warm_answer_p95_at_most_500_ms": sorted(durations)[int(len(durations) * 0.95 + 0.999) - 1] <= 500,
        "csp_violations_observed": sum(len(row["csp_violations"]) for row in browser["samples"]),
    }
    report = {
        "date": "2026-10-27",
        "production_build_id": build_id,
        "measurement_mode": "final-build-smoke" if quick else "full-lab",
        "api_reused_from_build_id": previous["production_build_id"] if quick else None,
        "synthetic": True,
        "upstream_provider_calls": 0,
        "api": {
            "measured_this_run": not quick,
            "sample_count": len(durations),
            "warmup_answers_excluded": 5,
            "conditions": "Sequential loopback HTTP to warm API8005, real PostgreSQL, accepted answers only; excludes BFF/TLS/cloud cold starts",
            "median_ms": round(statistics.median(durations), 2),
            "p95_ms_nearest_rank": round(sorted(durations)[int(len(durations) * 0.95 + 0.999) - 1], 2),
            "max_ms": round(max(durations), 2),
            "samples_ms": [round(x, 2) for x in durations],
        },
        "browser": browser,
        "target_comparison": targets,
        "limitations": "Lab measurements only; not field INP/p75 or GCP deployment latency. Browser metrics approximate identified lab, not Lighthouse scoring.",
    }
    out = ROOT / (
        ".data/tasteduel-audit/performance-final-smoke.json"
        if quick
        else ".data/tasteduel-audit/performance.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    engine.dispose()
    print(
        json.dumps(
            {
                "status": "measured",
                "report": str(out.relative_to(ROOT)),
                "api_p95_ms": report["api"]["p95_ms_nearest_rank"],
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as failure:
        print(json.dumps({"status": "failed", "safe_error_type": type(failure).__name__}), file=sys.stderr)
        raise SystemExit(1)
