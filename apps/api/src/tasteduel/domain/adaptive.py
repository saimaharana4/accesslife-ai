"""Private deterministic solo selection; prediction performance is never preference.

Bands are within-snapshot engineering heuristics, not human-calibrated difficulty.
No provider, model, affinity mutation or public DTO belongs in this module.
"""

from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
import hmac
from uuid import UUID

SELECTION_VERSION = "solo-performance-v1"
LEGACY_SELECTION_VERSION = "fixed-path-v1"
BANDS = ("easy", "medium", "hard")


@dataclass(frozen=True)
class SelectionPair:
    id: UUID
    entities: frozenset[UUID]
    band: str
    categories: frozenset[str] = frozenset()


@dataclass(frozen=True)
class PerformanceRound:
    pair: SelectionPair
    correct: bool
    winner_side: str


@dataclass(frozen=True)
class Selection:
    pair_id: UUID
    requested_band: str
    selected_band: str
    reason: str
    correct_streak: int
    winner_side: str
    policy_version: str = SELECTION_VERSION


class InsufficientContinuation(ValueError):
    """No fully valid five-round continuation can be proved from the saved pool."""


def choose_next(
    pairs: tuple[SelectionPair, ...],
    history: tuple[PerformanceRound, ...],
    *,
    selection_seed: bytes,
    min_categories: int = 0,
    min_bands: int = 1,
) -> Selection:
    """Select only an edge that retains an exact no-repeat complete continuation.

    A two-correct streak raises one band (again after each two consecutive correct
    predictions); a miss eases one band. Missing feasible bands fall back by
    nearest band, easier first on equal distance. The fallback is recorded.
    """
    if not 0 <= len(history) < 5 or not 1 <= len(pairs) <= 15:
        raise ValueError("bounded five-round pool required")
    if not isinstance(selection_seed, bytes) or len(selection_seed) != 32:
        raise ValueError("private 256-bit selection seed required")
    if type(min_categories) is not int or not 0 <= min_categories <= 10:
        raise ValueError("invalid category requirement")
    if type(min_bands) is not int or not 1 <= min_bands <= 3:
        raise ValueError("invalid band requirement")
    if len({pair.id for pair in pairs}) != len(pairs) or any(
        len(pair.entities) != 2 or pair.band not in BANDS for pair in pairs
    ):
        raise ValueError("invalid private pool")
    known = {pair.id: pair for pair in pairs}
    used: frozenset[UUID] = frozenset()
    for played in history:
        if (
            known.get(played.pair.id) != played.pair
            or played.pair.entities & used
            or type(played.correct) is not bool
            or played.winner_side not in ("left", "right")
        ):
            raise ValueError("invalid accepted prediction history")
        used |= played.pair.entities
    seen_categories = frozenset(category for row in history for category in row.pair.categories)
    seen_bands = frozenset(row.pair.band for row in history)
    available = tuple(pair for pair in pairs if not pair.entities & used)
    streak = 0
    for played in reversed(history):
        if not played.correct:
            break
        streak += 1
    target = BANDS.index(history[-1].pair.band) if history else 1
    if history and not history[-1].correct:
        target = max(0, target - 1)
    elif streak and streak % 2 == 0:
        target = min(2, target + 1)
    requested = BANDS[target]

    @lru_cache(maxsize=None)
    def continuation(
        remaining: tuple[int, ...], needed: int, categories: frozenset[str], bands: frozenset[str]
    ) -> bool:
        if needed == 0:
            return len(categories) >= min_categories and len(bands) >= min_bands
        if len(remaining) < needed:
            return False
        for offset, index in enumerate(remaining):
            pair = available[index]
            rest = tuple(
                other for other in remaining[offset + 1 :] if not available[other].entities & pair.entities
            )
            if continuation(rest, needed - 1, categories | pair.categories, bands | {pair.band}):
                return True
        return False

    feasible = []
    for index, pair in enumerate(available):
        rest = tuple(
            other
            for other in range(len(available))
            if other != index and not available[other].entities & pair.entities
        )
        if continuation(rest, 4 - len(history), seen_categories | pair.categories, seen_bands | {pair.band}):
            feasible.append(pair)
    if not feasible:
        raise InsufficientContinuation("saved pool cannot complete five valid nonrepeating rounds")
    chosen = min(
        feasible,
        key=lambda pair: (
            abs(BANDS.index(pair.band) - target),
            BANDS.index(pair.band) > target,
            -len(pair.categories - seen_categories),
            pair.band in seen_bands,
            hmac.digest(selection_seed, f"{SELECTION_VERSION}:{len(history)}:{pair.id}".encode(), sha256),
        ),
    )
    # Favor balanced 2/3 splits without forcing any future winner. Every complete
    # side pattern has positive weight: a hard 3/2 quota leaks round five for a
    # 3/1 prefix. Public IDs never reproduce this private deterministic draw.
    weighted_patterns = tuple(
        pattern for pattern in range(32) for _ in range(4 if pattern.bit_count() in (2, 3) else 1)
    )
    draw = int.from_bytes(hmac.digest(selection_seed, b"side-pattern", sha256))
    pattern = weighted_patterns[draw % len(weighted_patterns)]
    side = ("left", "right")[(pattern >> len(history)) & 1]
    return Selection(
        chosen.id,
        requested,
        chosen.band,
        "requested_band" if chosen.band == requested else "scarce_feasible_band",
        streak,
        side,
    )
