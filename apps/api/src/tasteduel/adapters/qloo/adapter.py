"""Allowlisted typed Qloo workflows. Provider JSON is consumed here, never by React/domain."""

import hashlib
import json
from uuid import UUID

from tasteduel.adapters.qloo.normalization import normalize_result
from tasteduel.adapters.qloo.process import ManagedMcpProcess, McpFailure
from tasteduel.ports.qloo import ProviderFailure, QlooResult, RankedCandidatesRequest, ResolveSeedRequest


class QlooMcpAdapter:
    def __init__(self, process: ManagedMcpProcess):
        self.process = process

    async def resolve_seed(self, request: ResolveSeedRequest) -> QlooResult:
        if request.domain not in {"artist", "movie"} or not 1 <= len(request.query.strip()) <= 200:
            return QlooResult("error", error=ProviderFailure("INVALID_SEED_REQUEST"))
        return await self._call(
            "describe", {"entity": request.query.strip(), "type": request.domain}, request.domain
        )

    async def ranked_candidates(self, request: RankedCandidatesRequest) -> QlooResult:
        if (
            request.seed_domain not in {"artist", "movie"}
            or request.target_domain not in {"artist", "movie"}
            or not isinstance(request.seed_id, UUID)
            or type(request.limit) is not int
            or not 1 <= request.limit <= 20
        ):
            return QlooResult("error", error=ProviderFailure("INVALID_RANKING_REQUEST"))
        # Resolved UUID, never a guessed name. Cold IDs may still cost a counted hydration request.
        arguments = {
            "target_type": request.target_domain,
            "signals": [str(request.seed_id)],
            "limit": request.limit,
            "explain": True,
        }
        return await self._call("recommend", arguments, request.target_domain)

    async def _call(self, operation, arguments, domain):
        fingerprint = hashlib.sha256(
            json.dumps(
                {"operation": operation, "arguments": arguments, "harness": "0.1.26"}, sort_keys=True
            ).encode()
        ).hexdigest()
        try:
            result = await self.process.call_tool("qloo_" + operation, arguments)
        except McpFailure as failure:
            return QlooResult(
                "error",
                error=ProviderFailure(
                    failure.code,
                    failure.code
                    in {
                        "MCP_DEADLINE",
                        "MCP_PROCESS_EXIT",
                        "MCP_STARTUP_TIMEOUT",
                    },
                ),
            )
        statuses = result.get("_tasteduel_http_statuses", ())
        if any(status in {401, 403} for status in statuses):
            return QlooResult("error", error=ProviderFailure("QLOO_AUTHENTICATION_FAILED"))
        if 429 in statuses:
            return QlooResult("error", error=ProviderFailure("QLOO_RATE_LIMITED", True))
        if any(type(status) is int and 500 <= status <= 599 for status in statuses):
            return QlooResult("error", error=ProviderFailure("QLOO_UPSTREAM_UNAVAILABLE", True))
        payload = result.get("structuredContent")
        if not isinstance(payload, dict):
            return QlooResult("error", error=ProviderFailure("PROVIDER_CONTRACT_INVALID"))
        return normalize_result(payload, operation=operation, domain=domain, context_hash=fingerprint)
