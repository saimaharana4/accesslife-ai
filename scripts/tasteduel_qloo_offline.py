"""Offline packaged-runtime check: no credentials, database or upstream requests."""

import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/api/src"))

from tasteduel.adapters.qloo.process import ManagedMcpProcess  # noqa: E402


async def check():
    attempts = []

    async def forbid(path):
        attempts.append(path)
        raise RuntimeError("OFFLINE_CHECK_FORBIDS_NETWORK")

    process = ManagedMcpProcess(
        runner=Path(__file__).resolve().parents[1] / "runtime/qloo/runner.mjs",
        api_key=None,
        reserve_upstream=forbid,
    )
    try:
        await process.start()
        assert process.ready and len(process.tool_schemas) == 3
        child = process._process
    finally:
        await process.close()
    assert child.returncode is not None and not attempts
    print(
        json.dumps(
            {
                "harness": "0.1.26",
                "allowed_workflows": 3,
                "upstream_requests": len(attempts),
                "child_reaped": True,
            }
        )
    )


if __name__ == "__main__":
    asyncio.run(check())
