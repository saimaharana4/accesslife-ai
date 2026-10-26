"""Private deterministic game evidence; never an HTTP response schema."""

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Literal
from uuid import UUID

Domain = Literal["artist", "movie"]
Band = Literal["easy", "medium", "hard"]


@dataclass(frozen=True)
class Category:
    label: str
    source: str


@dataclass(frozen=True)
class Candidate:
    id: UUID
    name: str
    domain: Domain
    affinity: float | None
    position: int
    context_hash: str
    ambiguous: bool = False
    categories: tuple[Category, ...] = ()
    image_url: str | None = None
    image_rights_verified: bool = False


@dataclass(frozen=True)
class RankingSnapshot:
    context_hash: str
    domain: Domain
    seed_id: UUID
    seed_domain: Domain
    candidates: tuple[Candidate, ...]
    ordering_verified: bool
    provider: str = "qloo"
    harness_version: str = "0.1.26"
    score_field: str = "query.affinity"


@dataclass(frozen=True)
class PairQualityPolicy:
    """Engineering heuristics, not calibrated human difficulty/confidence."""

    version: str = "duel-pool-v1"
    rounds: int = 5
    target_pairs: int = 15
    min_categories: int = 0
    min_bands: int = 1
    near_tie_ratio: float = 0.05
    max_candidates: int = 20

    def __post_init__(self) -> None:
        # Bounds also make exact graph evaluation finite and reproducible.
        if self.version != "duel-pool-v1":
            raise ValueError("unsupported policy version")
        integer_fields = (
            self.rounds,
            self.target_pairs,
            self.min_categories,
            self.min_bands,
            self.max_candidates,
        )
        if any(type(value) is not int for value in integer_fields):
            raise ValueError("policy counts must be integers")
        if self.rounds != 5 or not 10 <= self.target_pairs <= 15:
            raise ValueError("policy requires five rounds and a 10-15 pair target")
        if not 10 <= self.max_candidates <= 20:
            raise ValueError("candidate limit must be between ten and twenty")
        if not 0 <= self.min_categories <= 10 or not 1 <= self.min_bands <= 3:
            raise ValueError("invalid diversity requirements")
        if type(self.near_tie_ratio) is not float or self.near_tie_ratio != 0.05:
            raise ValueError("v1 fixes the relative near-tie threshold at 0.05")

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()
        return sha256(encoded).hexdigest()


@dataclass(frozen=True)
class PrivatePair:
    id: UUID
    first: Candidate
    second: Candidate
    winner_id: UUID
    band: Band
    relative_gap: float
    categories: frozenset[str] = frozenset()

    @property
    def entity_ids(self) -> frozenset[UUID]:
        return frozenset((self.first.id, self.second.id))


@dataclass(frozen=True)
class PresentedChoice:
    """Private delivery preparation; explicit API projection is still mandatory."""

    id: UUID
    entity: Candidate
    artwork_mode: Literal["approved_provider", "owned_fallback"]
    artwork_url: str | None


@dataclass(frozen=True)
class OrientedPair:
    pair_id: UUID
    left: PresentedChoice
    right: PresentedChoice
    winner_side: Literal["left", "right"]

    @property
    def left_choice_id(self) -> UUID:
        return self.left.id

    @property
    def right_choice_id(self) -> UUID:
        return self.right.id


@dataclass(frozen=True)
class PoolEvaluation:
    """Aggregate validator feedback safe for a bounded curator, not a browser."""

    policy_version: str
    status: Literal["ready", "insufficient_coverage", "invalid_snapshot", "evaluation_limited"]
    candidates_received: int
    candidates_accepted: int
    candidates_rejected: int
    candidate_rejections: tuple[tuple[str, int], ...]
    pair_rejections: tuple[tuple[str, int], ...]
    eligible_pair_count: int
    pair_count: int
    domain: Domain
    context_hash: str
    categories_available: int
    candidates_without_categories: int
    categories_required: int
    categories_in_path: int
    bands_available: tuple[Band, ...]
    bands_required: int
    bands_in_path: tuple[Band, ...]
    complete_path: bool
    diversity_satisfied: bool
    correction_reasons: tuple[str, ...]
    policy_fingerprint: str = ""
    search_limit_exceeded: bool = False
    objective_limited: bool = False
    objective: str = (
        "maximize sourced category coverage capped at ten, then within-snapshot gap-band coverage"
    )
    score_semantics: str = "within-snapshot engineering heuristic; no human calibration"


@dataclass(frozen=True)
class PoolBuildResult:
    status: Literal["ready", "insufficient_coverage", "invalid_snapshot", "evaluation_limited"]
    pairs: tuple[PrivatePair, ...]
    path: tuple[OrientedPair, ...]
    evaluation: PoolEvaluation
    policy: PairQualityPolicy = field(default_factory=PairQualityPolicy)
