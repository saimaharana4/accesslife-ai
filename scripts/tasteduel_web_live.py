"""Explicit local Prompt 10 live preview, with a persistent non-renewing budget.

Run with --serve after reviewing .data/tasteduel-prompt10/live-budget.json.
No cloud resources are changed. ADC and Secret Manager values stay in memory.
"""

import argparse
import asyncio
import hashlib
import importlib.util
import json
import logging
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))
ARTIFACTS = ROOT / ".data/tasteduel-prompt10"


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LiveBudget:
    """One API process, sequential admission; persist counts before dispatch."""

    def __init__(self):
        self.path = ARTIFACTS / "live-budget.json"
        self.data = json.loads(self.path.read_text(encoding="utf-8-sig"))
        if self.data.get("closed") or (self.data["qloo_ceiling"], self.data["vertex_ceiling"]) != (8, 6):
            raise RuntimeError("Closed or unexpected live budget")
        self.phase = "web_journey"

    def save(self):
        self.path.write_text(json.dumps(self.data, indent=2) + "\n", encoding="utf-8")

    def reserve_qloo(self, path):
        from tasteduel.adapters.qloo_policy import AdmissionDenied

        if self.data["qloo_reserved"] >= self.data["qloo_ceiling"]:
            raise AdmissionDenied("ITERATION_QLOO_BUDGET_EXHAUSTED")
        self.data["qloo_reserved"] += 1
        self.data["events"].append({"kind": "qloo_reservation", "path": path})
        self.save()

    def dispatch_qloo(self, path):
        self.data["qloo_dispatched"] += 1
        self.data["events"].append({"kind": "qloo_dispatch", "path": path})
        self.save()

    async def vertex_request(self, request):
        if (
            not request.url.host
            or request.url.host != "aiplatform.googleapis.com"
            or not request.url.path.endswith(":generateContent")
        ):
            raise RuntimeError("Unexpected model destination")
        if self.data["vertex_dispatched"] >= self.data["vertex_ceiling"]:
            raise RuntimeError("Iteration model budget exhausted")
        self.data["vertex_dispatched"] += 1
        self.data["events"].append({"kind": "vertex_dispatch"})
        self.save()

    async def vertex_response(self, response):
        self.data["events"].append({"kind": "vertex_response", "status": response.status_code})
        self.save()


class LiveGenerator:
    agent = None

    async def curate(self, *args, **kwargs):
        if self.agent is None:
            raise RuntimeError("Live curator unavailable")
        return await self.agent.curate(*args, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true", required=True)
    parser.parse_args()
    ARTIFACTS.mkdir(exist_ok=True, parents=True)
    lock = ARTIFACTS / "live.lock"
    lock.mkdir()  # Never automatically remove a lock left by an interrupted owner.
    try:
        budget = LiveBudget()
        local = load_script("tasteduel_local")
        local.start()
        _, runtime_url = local.bootstrap()
        from tasteduel.persistence.db import local_engine
        from tasteduel.config import Settings
        from tasteduel.api.main import create_app
        from tasteduel.api.provider_runtime import _secret_payload, QlooRuntime
        from tasteduel.adapters.qloo.process import ManagedMcpProcess
        from tasteduel.adapters.qloo.adapter import QlooMcpAdapter
        from tasteduel.adapters.qloo.ranked_http import QlooRankedHttpAdapter
        from tasteduel.adapters.qloo_policy import GuardedQlooPort, PostgresAdmissionStore
        from tasteduel.agents.round_curator import RoundCuratorAgent
        import uvicorn

        engine = local_engine(runtime_url)
        generator = LiveGenerator()

        async def factory(settings, engine):
            # Cold ADC refresh is separate from the twenty-second game envelope.
            async with asyncio.timeout(20):
                key = await asyncio.to_thread(_secret_payload, settings.qloo_secret_version)

            async def reserve(path):
                await guarded.reserve_upstream(path)
                budget.reserve_qloo(path)

            def dispatch(path):
                guarded.note_dispatch(path)
                budget.dispatch_qloo(path)

            process = ManagedMcpProcess(
                runner=ROOT / "runtime/qloo/runner.mjs",
                api_key=key,
                reserve_upstream=reserve,
                note_dispatch=dispatch,
            )
            raw = QlooRankedHttpAdapter(
                QlooMcpAdapter(process),
                api_key=key,
                reserve_upstream=reserve,
                note_dispatch=dispatch,
                typed_search=True,
            )
            guarded = GuardedQlooPort(
                raw, PostgresAdmissionStore(engine), hashlib.sha256(key.encode()).hexdigest()
            )
            model = None
            try:
                await process.start()
                model = await load_script("tasteduel_curator_live").vertex_model(budget)
                generator.agent = RoundCuratorAgent(
                    provider=guarded, model=model, capabilities={"artist": ("movie",), "movie": ("artist",)}
                )

                class Runtime(QlooRuntime):
                    async def close(self):
                        await model.aclose()
                        await super().close()

                return Runtime(guarded, process, raw)
            except BaseException:
                if model:
                    await model.aclose()
                await raw.close()
                await process.close()
                raise

        app = create_app(
            Settings(
                cookie_secure=False,
                qloo_enabled=True,
                generation_enabled=False,
                allowed_origins=("http://127.0.0.1:3001", "http://127.0.0.1:3003"),
            ),
            engine=engine,
            generator=generator,
            qloo_factory=factory,
        )
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("google").setLevel(logging.WARNING)
        print(
            "Bounded live Taste Duel API: http://127.0.0.1:8004 (8 Qloo / 6 Vertex ceiling; no credential output)"
        )
        uvicorn.run(app, host="127.0.0.1", port=8004, access_log=False, log_level="warning")
        engine.dispose()
    finally:
        lock.rmdir()


if __name__ == "__main__":
    try:
        main()
    except Exception as failure:
        print(json.dumps({"status": "failed", "safe_error_type": type(failure).__name__}))
        raise SystemExit(1)
