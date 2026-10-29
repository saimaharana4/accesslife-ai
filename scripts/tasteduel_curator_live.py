"""Explicit bounded live checks. Never print/save credentials or provider payloads.

The curator ledger is persistent: resuming does not renew its eight Qloo/five
Vertex ceilings. No infrastructure or application endpoint is changed here.
"""

import argparse
import asyncio
import importlib.util
import json
import logging
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))

import httpx  # noqa: E402
from tasteduel.adapters.vertex_curator import VertexCuratorModel, MODEL, LOCATION  # noqa: E402

ARTIFACTS = ROOT / ".data/tasteduel-curator"
PROJECT = "project-bb13ecd8-9d67-408d-9a7"


class LiveBudget:
    def __init__(self):
        self.path = ARTIFACTS / "live-budget.json"
        if not self.path.is_file():
            raise RuntimeError("A reviewed live budget must exist before any call")
        self.data = json.loads(self.path.read_text(encoding="utf-8"))
        if self.data["qloo_ceiling"] != 8 or self.data["vertex_ceiling"] != 5:
            raise RuntimeError("Unexpected live budget")
        if self.data.get("closed"):
            raise RuntimeError("This iteration is closed; do not renew its live budget")
        self.phase = "model_smoke"

    def save(self):
        self.path.write_text(json.dumps(self.data, indent=2) + "\n", encoding="utf-8")

    async def vertex_request(self, request):
        if (
            not request.url.host
            or not request.url.host.endswith("aiplatform.googleapis.com")
            or not request.url.path.endswith(":generateContent")
        ):
            raise RuntimeError("Unapproved Vertex request")
        if self.data["vertex_dispatched"] >= 5:
            raise RuntimeError("Vertex live budget exhausted")
        self.data["vertex_dispatched"] += 1
        self.data["events"].append(
            {
                "kind": "vertex",
                "ordinal": self.data["vertex_dispatched"],
                "phase": self.phase,
                "status": "dispatch",
            }
        )
        self.save()

    async def vertex_response(self, response):
        self.data["events"].append(
            {"kind": "vertex_response", "phase": self.phase, "status": response.status_code}
        )
        self.save()

    def reserve_qloo(self, path):
        from tasteduel.adapters.qloo_policy import AdmissionDenied

        if self.data["qloo_reserved"] >= 8:
            raise AdmissionDenied("ITERATION_QLOO_BUDGET_EXHAUSTED")
        self.data["qloo_reserved"] += 1
        self.data["events"].append(
            {
                "kind": "qloo_reservation",
                "phase": self.phase,
                "path": path,
                "ordinal": self.data["qloo_reserved"],
            }
        )
        self.save()

    def dispatch_qloo(self, path):
        self.data["qloo_dispatched"] += 1
        self.data["events"].append(
            {
                "kind": "qloo_dispatch",
                "phase": self.phase,
                "path": path,
                "ordinal": self.data["qloo_dispatched"],
            }
        )
        self.save()


async def vertex_model(budget):
    import google.auth
    from google import genai
    from google.genai import types

    # ADC is resolved by the SDK; no application code inspects credential files.
    credentials, _ = await asyncio.to_thread(
        google.auth.default, scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    transport = httpx.AsyncClient(
        timeout=8,
        trust_env=False,
        event_hooks={"request": [budget.vertex_request], "response": [budget.vertex_response]},
    )
    client = genai.Client(
        vertexai=True,
        project=PROJECT,
        location=LOCATION,
        credentials=credentials,
        http_options=types.HttpOptions(
            api_version="v1",
            timeout=8000,
            retry_options=types.HttpRetryOptions(attempts=1),
            httpx_async_client=transport,
        ),
    )
    return VertexCuratorModel(project=PROJECT, client=client)


async def smoke(budget):
    budget.phase = "model_smoke"
    model = await vertex_model(budget)
    tool = {
        "name": "inspect_seed",
        "description": "Inspect the already confirmed cultural seed.",
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
    }
    started = time.monotonic()
    try:
        turn = await model.decide(
            ({"role": "user", "data": {"instruction": "Call inspect_seed with no arguments."}},),
            (tool,),
            timeout_seconds=8,
        )
        okay = len(turn.calls) == 1 and turn.calls[0].name == "inspect_seed" and turn.calls[0].arguments == {}
        report = {
            "phase": "model_smoke",
            "status": "ok" if okay else "unexpected_tool",
            "model": MODEL,
            "location": LOCATION,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "input_tokens": turn.input_tokens,
            "output_tokens": turn.output_tokens,
            "usage_complete": turn.usage_complete,
            "native_function_call_verified": okay,
        }
    finally:
        await model.aclose()
    (ARTIFACTS / "model-smoke.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


async def agent_live(budget):
    import secrets
    from uuid import uuid4

    from tasteduel.adapters.qloo.adapter import QlooMcpAdapter
    from tasteduel.adapters.qloo.process import ManagedMcpProcess
    from tasteduel.adapters.qloo.ranked_http import QlooRankedHttpAdapter
    from tasteduel.adapters.qloo_policy import GuardedQlooPort, PostgresAdmissionStore
    from tasteduel.agents.round_curator import RoundCuratorAgent
    from tasteduel.api.provider_runtime import _secret_payload
    from tasteduel.config import Settings
    from tasteduel.persistence.db import local_engine
    from tasteduel.ports.qloo import ResolveSeedRequest
    import hashlib

    spec = importlib.util.spec_from_file_location("isolated_local_setup", ROOT / "scripts/tasteduel_local.py")
    local = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(local)
    local.start()
    _, runtime_url = local.bootstrap()  # Dedicated local credentials; never printed/persisted here.
    engine = local_engine(runtime_url)
    settings = Settings(qloo_enabled=False)
    async with asyncio.timeout(5):
        key = await asyncio.to_thread(_secret_payload, settings.qloo_secret_version)
    store = PostgresAdmissionStore(engine)

    async def reserve(path):
        await guarded.reserve_upstream(path)
        budget.reserve_qloo(path)

    def dispatch(path):
        guarded.note_dispatch(path)
        budget.dispatch_qloo(path)

    process = ManagedMcpProcess(
        runner=ROOT / "runtime/qloo/runner.mjs", api_key=key, reserve_upstream=reserve, note_dispatch=dispatch
    )
    raw = QlooRankedHttpAdapter(
        QlooMcpAdapter(process),
        api_key=key,
        reserve_upstream=reserve,
        note_dispatch=dispatch,
        typed_search=True,
    )
    guarded = GuardedQlooPort(raw, store, hashlib.sha256(key.encode()).hexdigest())
    report = {
        "phase": "capability_and_agent",
        "ranking_transport": "http_ranked",
        "resolution_transport": "explicit_typed_http_search",
        "capabilities": [],
        "model": MODEL,
        "location": LOCATION,
        "cloud_changes": False,
    }
    model = None
    try:
        await process.start()  # initialize/listTools/checksum: zero upstream requests.
        budget.phase = "capability"
        # Artist -> movie has an exact raw typed cross-domain feasibility record
        # in capability; fresh agent output still must pass the actual P7 validator.
        verified = ["movie"]
        report["historical_capability_reference"] = "ai/qloo-capability-matrix.md: artist -> movie, capability"
        async with guarded.request_budget(max_requests=6, deadline_seconds=20):
            lookup = await guarded.resolve_seed(ResolveSeedRequest("Radiohead", "artist"))
            if lookup.status != "ok" or len(lookup.entities) != 1:
                report.update(
                    status="seed_resolution_blocked",
                    resolution_status=lookup.status,
                    failure_code=lookup.error.code if lookup.error else None,
                )
                return
            seed = lookup.entities[0]
        if not verified:
            report["status"] = "capability_blocked"
            return
        budget.phase = "agent"
        model = await vertex_model(budget)
        agent = RoundCuratorAgent(provider=guarded, model=model, capabilities={seed.domain: tuple(verified)})
        outcome = await agent.curate(
            seed, game_id=uuid4(), rng_seed=secrets.token_hex(32), allow_fallback=False
        )
        # Minimal private execution evidence only. No normalized rows, pairs, raw
        # provider/model responses, prompts, signatures or secret payloads retained.
        receipt = outcome.receipt.model_dump(mode="json")
        receipt.pop("seed_entity_id", None)
        receipt.pop("game_id", None)
        report.update(
            status="ok" if outcome.pool else "agent_gate_failed",
            failure_code=outcome.failure_code,
            receipt=receipt,
            native_tool_use_verified=bool(outcome.pool)
            and outcome.receipt.curator_mode.value == "genuine_agent"
            and any(action.action == "model_request" and action.status == "ok" for action in outcome.trace)
            and any(action.action == "fetch_ranked" and action.status == "ok" for action in outcome.trace)
            and any(action.action == "finish_pool" and action.status == "ok" for action in outcome.trace),
            real_ranking_pool_verified=bool(outcome.pool),
            natural_correction_observed=outcome.receipt.bounded_correction_count > 0,
        )
    finally:
        if model:
            await model.aclose()
        await raw.close()
        await process.close()
        engine.dispose()
        report["counts"] = {
            key: budget.data[key] for key in ("qloo_reserved", "qloo_dispatched", "vertex_dispatched")
        }
        (ARTIFACTS / "live-summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "status": report.get("status", "interrupted"),
                    "counts": report["counts"],
                    "capabilities": [
                        {
                            key: entry[key]
                            for key in ("target_domain", "status", "normalized_count", "ordering_verified")
                        }
                        for entry in report["capabilities"]
                    ],
                    "real_ranking_pool_verified": report.get("real_ranking_pool_verified", False),
                    "natural_correction_observed": report.get("natural_correction_observed", False),
                    "failure_code": report.get("failure_code"),
                }
            )
        )


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-smoke", action="store_true")
    parser.add_argument("--agent-live", action="store_true")
    args = parser.parse_args()
    if args.model_smoke == args.agent_live:
        parser.error("Choose exactly one explicit live check")
    ARTIFACTS.mkdir(exist_ok=True, parents=True)
    lock = ARTIFACTS / "live.lock"
    lock.mkdir()  # Exclusive owner. A leftover lock requires review; never reset a spent ledger.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    try:
        budget = LiveBudget()
        if args.model_smoke:
            await smoke(budget)
        else:
            await agent_live(budget)
    finally:
        lock.rmdir()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as failure:
        # No exception string, request/response, SDK diagnostics or local secret path.
        print(json.dumps({"status": "failed", "safe_error_type": type(failure).__name__}))
        raise SystemExit(1)
