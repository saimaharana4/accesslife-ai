"""Private, provider-independent deterministic duel-pool engine."""

from .builder import SearchBudgetExceeded, build_pool, continuation_options, find_path, orient_path
from .types import (
    Band,
    Candidate,
    Category,
    OrientedPair,
    PairQualityPolicy,
    PoolBuildResult,
    PoolEvaluation,
    PresentedChoice,
    PrivatePair,
    RankingSnapshot,
)
from .validation import ValidationResult, validate_snapshot

__all__ = [
    "Band",
    "Candidate",
    "Category",
    "OrientedPair",
    "PairQualityPolicy",
    "PoolBuildResult",
    "PoolEvaluation",
    "PresentedChoice",
    "PrivatePair",
    "RankingSnapshot",
    "SearchBudgetExceeded",
    "ValidationResult",
    "build_pool",
    "continuation_options",
    "find_path",
    "orient_path",
    "validate_snapshot",
]
