"""API composition root. No credentials/provider I/O on import or OpenAPI export."""

import asyncio
from dataclasses import dataclass
import hashlib
from pathlib import Path

from sqlalchemy.engine import Engine

from tasteduel.adapters.qloo.adapter import QlooMcpAdapter
from tasteduel.adapters.qloo.process import ManagedMcpProcess, McpFailure
from tasteduel.adapters.qloo_policy import GuardedQlooPort, PostgresAdmissionStore
from tasteduel.config import Settings


class ProviderStartupFailure(Exception):
    def __init__(self, code="QLOO_STARTUP_UNAVAILABLE"):
        self.code = code
        super().__init__(code)


def _secret_payload(reference: str) -> str:
    # The application does not inspect credential files; the SDK resolves server ADC.
    from google.cloud import secretmanager

    with secretmanager.SecretManagerServiceClient() as client:
        response = client.access_secret_version(request={"name": reference}, retry=None, timeout=5)
        value = response.payload.data.decode("utf-8")
    if not 16 <= len(value) <= 512 or any(char.isspace() for char in value):
        raise ProviderStartupFailure("QLOO_CREDENTIAL_INVALID")
    return value


@dataclass
class QlooRuntime:
    port: GuardedQlooPort
    process: ManagedMcpProcess

    async def close(self):
        await self.process.close()


async def build_qloo_runtime(settings: Settings, engine: Engine) -> QlooRuntime:
    process = None
    try:
        async with asyncio.timeout(settings.qloo_startup_timeout):
            key = await asyncio.to_thread(_secret_payload, settings.qloo_secret_version)
        scope = hashlib.sha256(key.encode()).hexdigest()
        store = PostgresAdmissionStore(engine, requests_per_minute=settings.qloo_requests_per_minute)

        async def reserve(path):
            await guarded.reserve_upstream(path)

        process = ManagedMcpProcess(
            node=settings.qloo_node_path,
            runner=Path(settings.qloo_runner_path),
            api_key=key,
            reserve_upstream=reserve,
            startup_timeout=settings.qloo_startup_timeout,
            call_timeout=settings.qloo_call_timeout,
            max_restarts=settings.qloo_max_restarts,
        )
        guarded = GuardedQlooPort(QlooMcpAdapter(process), store, scope)
        await process.start()  # initialize/listTools/capabilities are offline; no upstream fetch.
        return QlooRuntime(guarded, process)
    except asyncio.CancelledError:
        if process:
            await process.close()
        raise
    except Exception as failure:
        if process:
            await process.close()
        code = (
            failure.code
            if isinstance(failure, (McpFailure, ProviderStartupFailure))
            else "QLOO_STARTUP_UNAVAILABLE"
        )
        raise ProviderStartupFailure(code) from None
