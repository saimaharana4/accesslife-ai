"""Private, typed provider values. None of these records is a browser DTO."""

from dataclasses import dataclass
from datetime import datetime
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


@dataclass(frozen=True)
class ProviderFailure:
    code: str
    retryable: bool = False


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
