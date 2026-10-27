"""Opt-in sequential quality matrix; fixed eight-send ledger, no raw captures.

Uses the reviewed typed-HTTP escape hatch, not a fabricated MCP workflow.
ADC/Secret Manager payloads remain in memory. Reruns never renew this ledger.
"""

import argparse
import asyncio
from datetime import UTC, datetime, timedelta
import hashlib
import importlib.util
import json
import logging
from pathlib import Path
import secrets
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))
sys.path.insert(0, str(ROOT / "scripts"))
ARTIFACTS = ROOT / ".data/tasteduel-quality"
MATRIX = (
    ("Radiohead", "artist", "movie"),
    ("Beyoncé", "artist", "movie"),
    ("Inception", "movie", "artist"),
    ("Spirited Away", "movie", "artist"),
)


class QualityBudget:
    def __init__(self, path):
        self.path = path
        self.data = json.loads(path.read_text(encoding="utf-8"))
        if (
            self.data.get("closed") or self.data.get("ceiling") != 8
            or type(self.data.get("dispatched")) is not int
            or not 0 <= self.data["dispatched"] <= 8
        ):
            raise RuntimeError("Closed or unexpected quality budget")

    def save(self):
        self.path.write_text(json.dumps(self.data, indent=2) + "\n", encoding="utf-8")

    def dispatch(self, path):
        if path not in ("/search", "/v2/insights") or self.data["dispatched"] >= 8:
            raise RuntimeError("Quality request budget exhausted")
        self.data["dispatched"] += 1
        self.data["events"].append({"path": path, "ordinal": self.data["dispatched"]})
        self.save()  # A failed or interrupted send is consumed, never replenished.


async def run(budget):
    from tasteduel.adapters.qloo.adapter import QlooMcpAdapter
    from tasteduel.adapters.qloo.process import ManagedMcpProcess
    from tasteduel.adapters.qloo.ranked_http import QlooRankedHttpAdapter
    from tasteduel.adapters.qloo_policy import GuardedQlooPort, PostgresAdmissionStore
    from tasteduel.api.provider_runtime import _secret_payload
    from tasteduel.application.pool_preparation import prepare_qloo_pool
    from tasteduel.config import Settings
    from tasteduel.persistence.db import local_engine
    from tasteduel.ports.qloo import RankedCandidatesRequest, ResolveSeedRequest
    from tasteduel_round_quality import audit_prepared_pool

    spec = importlib.util.spec_from_file_location("quality_local_setup", ROOT / "scripts/tasteduel_local.py")
    local = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(local)
    local.start()
    _, runtime_url = local.bootstrap()
    engine = local_engine(runtime_url)
    settings = Settings()
    async with asyncio.timeout(20):
        key = await asyncio.to_thread(_secret_payload, settings.qloo_secret_version)
    store = PostgresAdmissionStore(engine)
    scope = hashlib.sha256(key.encode()).hexdigest()

    async def reserve(path):
        await guarded.reserve_upstream(path)

    def dispatch(path):
        budget.dispatch(path)
        guarded.note_dispatch(path)

    process = ManagedMcpProcess(
        runner=ROOT / "runtime/qloo/runner.mjs", api_key=key,
        reserve_upstream=reserve, note_dispatch=dispatch,
    )
    raw = QlooRankedHttpAdapter(
        QlooMcpAdapter(process), api_key=key,
        reserve_upstream=reserve, note_dispatch=dispatch, typed_search=True,
    )
    guarded = GuardedQlooPort(raw, store, scope)

    async def once(function, request):
        # Invoke the adapter directly to disable GuardedQlooPort's eligible retry;
        # its shared SQL admission and one-send context remain enforced.
        async with guarded.request_budget(max_requests=1, deadline_seconds=15):
            async with asyncio.timeout(15):
                result = await function(request)
        await store.record(scope, failed=result.status == "error", auth=bool(
            result.error and result.error.code == "QLOO_AUTHENTICATION_FAILED"
        ))
        await asyncio.sleep(0.25)
        return result

    reports = []
    try:
        await process.start()  # initialize/listTools only: zero upstream lookups.
        for label, source, target in MATRIX:
            started = time.monotonic()
            resolution = await once(raw.resolve_seed, ResolveSeedRequest(label, source))
            entry = {"seed_label": label, "seed_domain": source, "target_domain": target,
                     "resolution_status": resolution.status}
            if resolution.status != "ok" or len(resolution.entities) != 1:
                entry["status"] = "seed_selection_required_or_unavailable"
                reports.append(entry)
                if resolution.error:
                    entry["error_code"] = resolution.error.code
                    break
                continue  # Never silently select an ambiguous search result.
            seed = resolution.entities[0]
            request = RankedCandidatesRequest(seed.id, source, target)
            result = await once(raw.ranked_candidates, request)
            now = datetime.now(UTC)
            prepared = prepare_qloo_pool(
                result, request, rng_seed=secrets.token_hex(32), now=now,
                evidence_expires_at=now + timedelta(hours=1), confirmed_seed=seed,
            )
            entry.update(audit_prepared_pool(result, prepared))
            entry["elapsed_ms"] = round((time.monotonic() - started) * 1000)
            reports.append(entry)
            if result.error:
                entry["error_code"] = result.error.code
                break  # No repeated probes after auth, quota or provider failures.
        report = {
            "checked_at": datetime.now(UTC).isoformat(), "mode": "live_qloo_deterministic_quality_audit",
            "transport": "explicit_typed_http_gap_adapter", "vertex_requests": 0,
            "qloo_dispatched": budget.data["dispatched"], "qloo_ceiling": 8,
            "retries": 0, "raw_payloads_saved": False, "human_participants": 0,
            "cases": reports,
        }
        (ARTIFACTS / "quality-summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=True))
    finally:
        await raw.close()
        await process.close()
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--initialize-budget", action="store_true")
    parser.add_argument("--run-live", action="store_true")
    args = parser.parse_args()
    if args.initialize_budget == args.run_live:
        parser.error("Choose exactly one explicit operation")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    path = ARTIFACTS / "live-budget.json"
    if args.initialize_budget:
        with path.open("x", encoding="utf-8") as output:
            json.dump({"ceiling": 8, "dispatched": 0, "vertex_ceiling": 0,
                       "closed": False, "events": []}, output, indent=2)
        print("Initialized non-renewing eight-request quality budget; no provider call.")
        return
    lock = ARTIFACTS / "live.lock"
    lock.mkdir()  # An interrupted owner's lock is never silently adopted.
    budget = None
    try:
        budget = QualityBudget(path)
        logging.disable(logging.CRITICAL)  # No HTTP/provider diagnostics or payloads.
        asyncio.run(run(budget))
    finally:
        if budget:
            budget.data["closed"] = True
            budget.save()
        lock.rmdir()


if __name__ == "__main__":
    try:
        main()
    except Exception as failure:
        print(json.dumps({"status": "blocked", "safe_error_type": type(failure).__name__}))
        raise SystemExit(1)
