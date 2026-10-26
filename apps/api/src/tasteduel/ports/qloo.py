"""Private, typed provider values. None of these records is a browser DTO."""

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import Literal, Protocol
from uuid import UUID

EntityDomain = Literal["artist", "movie"]
ProviderStatus = Literal["ok", "empty", "needs_input", "partial", "degraded", "error"]


@dataclass(frozen=True)
class ResolveSeedRequest:
    query: str
    domain: EntityDomain


@dataclass(frozen=True)
class RankedCandidatesRequest:
    seed_id: UUID
    seed_domain: EntityDomain
    target_domain: EntityDomain
    limit: int = 20


def ranked_context_hash(request: RankedCandidatesRequest, *, transport: str = "mcp") -> str:
    """Bind a normalized snapshot to the exact pinned MCP recommendation inputs.

    This is the existing Prompt 6 fingerprint, not a second provider schema.
    A future transport/filter change must version/review this contract too.
    """
    if transport == "http_ranked":
        value = {
            "transport": "qloo-http-affinity-v1",
            "host": "https://hackathon.api.qloo.com",
            "path": "/v2/insights",
            "parameters": ranked_http_parameters(request),
        }
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
    if transport != "mcp":
        raise ValueError("Unsupported ranking transport")
    arguments = {
        "target_type": request.target_domain,
        "signals": [str(request.seed_id)],
        "limit": request.limit,
        "explain": True,
    }
    value = {"operation": "recommend", "arguments": arguments, "harness": "0.1.26"}
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def ranked_http_parameters(request: RankedCandidatesRequest) -> dict[str, str]:
    return {
        "filter.type": "urn:entity:" + request.target_domain,
        "signal.interests.entities": str(request.seed_id),
        "take": str(request.limit),
        "feature.explainability": "true",
        "sort_by": "affinity",
    }


@dataclass(frozen=True)
class EntityMetadata:
    id: UUID
    name: str
    domain: EntityDomain
    image_url: str | None = None
    image_rights_verified: bool = False


@dataclass(frozen=True)
class RankedCandidate:
    entity: EntityMetadata
    affinity: float
    position: int
    # Compact MCP evidence does not establish raw source-field precedence or a licence.
    explanation: str | None = None


@dataclass(frozen=True)
class ResolutionIssue:
    kind: str
    choices: tuple[EntityMetadata, ...] = ()


@dataclass(frozen=True)
class RankingEvidence:
    context_hash: str
    observed_at: datetime
    provider: str = "qloo"
    harness_version: str = "0.1.26"
    score_field: str = "harness.compact.affinity"
    ordering_verified: bool = False
    source_label: str = "Qloo API via official harness"
    transport: Literal["mcp", "http_ranked"] = "mcp"


@dataclass(frozen=True)
class ProviderFailure:
    code: str
    retryable: bool = False
    retry_after_seconds: float | None = None


@dataclass(frozen=True)
class QlooResult:
    status: ProviderStatus
    entities: tuple[EntityMetadata, ...] = ()
    candidates: tuple[RankedCandidate, ...] = ()
    issues: tuple[ResolutionIssue, ...] = ()
    warnings: tuple[str, ...] = ()
    evidence: RankingEvidence | None = None
    error: ProviderFailure | None = None


class QlooPort(Protocol):
    async def resolve_seed(self, request: ResolveSeedRequest) -> QlooResult: ...
    async def ranked_candidates(self, request: RankedCandidatesRequest) -> QlooResult: ...
