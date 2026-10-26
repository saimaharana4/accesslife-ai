"""Bounded deterministic pool construction and exact continuation feasibility.

The objective prefers sourced category coverage, contestant coverage and gap-band
variation. These are engineering heuristics, not a claim of human surprise.
"""

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from hashlib import sha256
from itertools import combinations
import json
import random
from uuid import UUID

from .types import (
    Band,
    Candidate,
    OrientedPair,
    PairQualityPolicy,
    PoolBuildResult,
    PoolEvaluation,
    PresentedChoice,
    PrivatePair,
    RankingSnapshot,
)
from .validation import approved_image, category_labels, validate_snapshot

MAX_SEARCH_STATES = 25_000


class SearchBudgetExceeded(RuntimeError):
    """The bounded exact evaluator did not prove feasibility or impossibility."""


@dataclass
class _SearchBudget:
    states: int = 0

    def reserve(self) -> None:
        self.states += 1
        if self.states > MAX_SEARCH_STATES:
            raise SearchBudgetExceeded("exact matching state budget exhausted")


def _edge_key(pair: PrivatePair) -> tuple[str, str]:
    return tuple(sorted((str(pair.first.id), str(pair.second.id))))


def find_path(
    pairs: tuple[PrivatePair, ...],
    *,
    rounds: int = 5,
    used_entity_ids: frozenset[UUID] = frozenset(),
    min_categories: int = 0,
    min_bands: int = 1,
    seen_categories: frozenset[str] = frozenset(),
    seen_bands: frozenset[Band] = frozenset(),
    _budget: _SearchBudget | None = None,
) -> tuple[PrivatePair, ...] | None:
    """Exact bounded matching with journey-wide category/band constraints.

    Examines edges, not just independently valid pair counts. Public callers must
    never supply arbitrary graphs; this is a private pure-domain helper.
    """
    if (
        any(type(value) is not int for value in (rounds, min_categories, min_bands))
        or rounds < 0
        or rounds > 5
        or not 0 <= min_categories <= 10
        or not 0 <= min_bands <= 3
    ):
        raise ValueError("invalid continuation requirements")
    edges = tuple(
        sorted(
            (p for p in pairs if len(p.entity_ids) == 2 and not p.entity_ids & used_entity_ids), key=_edge_key
        )
    )
    ids = sorted({entity for pair in edges for entity in pair.entity_ids}, key=str)
    if len(ids) > 20:
        raise ValueError("matching graph exceeds bounded candidate capacity")
    index = {entity: i for i, entity in enumerate(ids)}
    categories = sorted({label for p in edges for label in p.categories} | set(seen_categories))
    cat_index = {label: i for i, label in enumerate(categories)}
    bands: tuple[Band, ...] = ("hard", "medium", "easy")
    band_index = {band: i for i, band in enumerate(bands)}
    edge_data = tuple(
        (
            sum(1 << index[e] for e in p.entity_ids),
            sum(1 << cat_index[c] for c in p.categories),
            1 << band_index[p.band],
        )
        for p in edges
    )
    by_vertex = tuple(
        tuple(i for i, (mask, _, _) in enumerate(edge_data) if mask & (1 << vertex))
        for vertex in range(len(ids))
    )
    initial_cats = sum(1 << cat_index[c] for c in seen_categories if c in cat_index)
    initial_bands = sum(1 << band_index[b] for b in seen_bands if b in band_index)
    budget = _budget or _SearchBudget()

    @lru_cache(maxsize=None)
    def search(available: int, needed: int, cats: int, band_mask: int) -> tuple[int, ...] | None:
        budget.reserve()
        if needed == 0:
            return () if cats.bit_count() >= min_categories and band_mask.bit_count() >= min_bands else None
        if available.bit_count() < needed * 2:
            return None
        possible_cats, possible_bands = cats, band_mask
        for mask, cat_mask, b_mask in edge_data:
            if mask & available == mask:
                possible_cats |= cat_mask
                possible_bands |= b_mask
        if possible_cats.bit_count() < min_categories or possible_bands.bit_count() < min_bands:
            return None
        vertex = (available & -available).bit_length() - 1
        choices = [i for i in by_vertex[vertex] if edge_data[i][0] & available == edge_data[i][0]]
        choices.sort(
            key=lambda i: (
                -((edge_data[i][1] & ~cats).bit_count()),
                -((edge_data[i][2] & ~band_mask).bit_count()),
                _edge_key(edges[i]),
            )
        )
        for i in choices:
            mask, cat_mask, b_mask = edge_data[i]
            result = search(available ^ mask, needed - 1, cats | cat_mask, band_mask | b_mask)
            if result is not None:
                return (i, *result)
        return search(available & ~(1 << vertex), needed, cats, band_mask)

    found = search((1 << len(ids)) - 1, rounds, initial_cats, initial_bands)
    return tuple(edges[i] for i in found) if found is not None else None


def _rng(snapshot: RankingSnapshot, seed: str | int) -> random.Random:
    # Canonical input makes results independent of response tuple permutation.
    payload = [snapshot.context_hash, snapshot.domain, str(seed)]
    return random.Random(
        int.from_bytes(sha256(json.dumps(payload, ensure_ascii=True).encode()).digest(), "big")
    )


def _opaque(rng: random.Random) -> UUID:
    return UUID(int=rng.getrandbits(128), version=4)


def orient_path(path: tuple[PrivatePair, ...], *, rng_seed: str | int) -> tuple[OrientedPair, ...]:
    """A shuffled balanced side schedule; IDs use an independent random stream.

    The seed is private server entropy in production, persisted with the game.
    It must never be sent to a client or replaced by a public context hash.
    """
    side_rng = random.Random(str(rng_seed) + ":sides")
    id_rng = random.Random(str(rng_seed) + ":ids")
    left_count = len(path) // 2 + (side_rng.randrange(2) if len(path) % 2 else 0)
    sides = ["left"] * left_count + ["right"] * (len(path) - left_count)
    side_rng.shuffle(sides)
    result: list[OrientedPair] = []
    for pair, side in zip(path, sides):
        winner, loser = (
            (pair.first, pair.second) if pair.first.id == pair.winner_id else (pair.second, pair.first)
        )
        left, right = (winner, loser) if side == "left" else (loser, winner)

        def choice(candidate: Candidate) -> PresentedChoice:
            image = approved_image(candidate)
            return PresentedChoice(
                _opaque(id_rng), candidate, "approved_provider" if image else "owned_fallback", image
            )

        result.append(OrientedPair(pair.id, choice(left), choice(right), side))
    return tuple(result)


def continuation_options(
    pool: PoolBuildResult,
    *,
    used_entity_ids: frozenset[UUID] = frozenset(),
    rounds_remaining: int = 5,
    seen_categories: frozenset[str] = frozenset(),
    seen_bands: frozenset[Band] = frozenset(),
) -> tuple[PrivatePair, ...]:
    """Only pairs that leave a full policy-compliant no-repeat continuation."""
    if pool.status != "ready" or not 1 <= rounds_remaining <= 5:
        return ()
    eligible = []
    budget = _SearchBudget()
    for pair in pool.pairs:
        if pair.entity_ids & used_entity_ids:
            continue
        remainder = find_path(
            pool.pairs,
            rounds=rounds_remaining - 1,
            used_entity_ids=used_entity_ids | pair.entity_ids,
            min_categories=pool.policy.min_categories,
            min_bands=pool.policy.min_bands,
            seen_categories=seen_categories | pair.categories,
            seen_bands=seen_bands | {pair.band},
            _budget=budget,
        )
        if remainder is not None:
            eligible.append(pair)
    return tuple(eligible)


def build_pool(
    snapshot: RankingSnapshot, *, rng_seed: str | int, policy: PairQualityPolicy = PairQualityPolicy()
) -> PoolBuildResult:
    validation = validate_snapshot(snapshot, policy)
    accepted = validation.accepted
    rng = _rng(snapshot, f"{rng_seed}:selection")
    id_rng = _rng(snapshot, f"{rng_seed}:pair-ids")
    pair_rejections: Counter[str] = Counter()
    all_pairs: list[PrivatePair] = []
    scores = {c.id: Decimal(str(c.affinity)) for c in accepted}
    spread = max(scores.values(), default=Decimal(0)) - min(scores.values(), default=Decimal(0))
    canonical_ids = sorted((c.id for c in accepted), key=str) if not validation.snapshot_reasons else []
    pair_ids = {frozenset(ids): _opaque(id_rng) for ids in combinations(canonical_ids, 2)}
    eligible_raw: list[tuple[Candidate, Candidate, float]] = []
    if not validation.snapshot_reasons:
        for first, second in combinations(accepted, 2):
            gap = scores[first.id] - scores[second.id]
            if gap == 0:
                pair_rejections["tied_score"] += 1
            elif spread <= 0 or gap / spread <= Decimal(str(policy.near_tie_ratio)):
                pair_rejections["near_tie"] += 1
            else:
                eligible_raw.append((first, second, float(gap / spread)))
        gaps = sorted({gap for _, _, gap in eligible_raw})
        for first, second, gap in eligible_raw:
            # Equal gap values always share a band; small distributions can expose fewer bands.
            percentile = gaps.index(gap) / max(1, len(gaps) - 1)
            band: Band = "hard" if percentile < 1 / 3 else "medium" if percentile < 2 / 3 else "easy"
            all_pairs.append(
                PrivatePair(
                    pair_ids[frozenset((first.id, second.id))],
                    first,
                    second,
                    first.id,
                    band,
                    gap,
                    category_labels(first) | category_labels(second),
                )
            )
    all_tuple = tuple(all_pairs)
    search_limited = False
    objective_limited = False
    budget = _SearchBudget()
    try:
        raw_path = find_path(
            all_tuple, min_categories=policy.min_categories, min_bands=policy.min_bands, _budget=budget
        )
    except SearchBudgetExceeded:
        search_limited = True
        raw_path = None
    if raw_path:
        best_category_count = len({label for pair in raw_path for label in pair.categories})
        upper_categories = min(10, len({label for pair in all_tuple for label in pair.categories}))
        try:
            # Exact feasibility upgrades under one shared state budget. These
            # improve the whole five-round journey, not just decorative extras.
            for target in range(upper_categories, best_category_count, -1):
                upgraded = find_path(
                    all_tuple, min_categories=target, min_bands=policy.min_bands, _budget=budget
                )
                if upgraded:
                    raw_path = upgraded
                    best_category_count = len({label for pair in raw_path for label in pair.categories})
                    break
            best_band_count = len({pair.band for pair in raw_path})
            for target in range(3, best_band_count, -1):
                upgraded = find_path(
                    all_tuple, min_categories=min(10, best_category_count), min_bands=target, _budget=budget
                )
                if upgraded:
                    raw_path = upgraded
                    break
        except SearchBudgetExceeded:
            # A proved complete path remains usable; the stronger objective is
            # explicitly unproved. Never treat this as mathematical insufficiency.
            objective_limited = True
    # Seed a complete witness path before adding adaptive alternatives. A greedy
    # list of 15 attractive edges alone can strand the fifth round.
    selected = list(raw_path or ())
    covered_entities = {entity for p in selected for entity in p.entity_ids}
    covered_categories = {category for p in selected for category in p.categories}
    covered_bands = {p.band for p in selected}
    tie_break = {p.id: rng.random() for p in all_tuple}
    while len(selected) < policy.target_pairs:
        remaining = [p for p in all_tuple if p not in selected]
        if not remaining:
            break
        best = max(
            remaining,
            key=lambda p: (
                len(p.categories - covered_categories),
                len(p.entity_ids - covered_entities),
                int(p.band not in covered_bands),
                -sum(bool(p.entity_ids & old.entity_ids) for old in selected),
                tie_break[p.id],
            ),
        )
        selected.append(best)
        covered_entities.update(best.entity_ids)
        covered_categories.update(best.categories)
        covered_bands.add(best.band)
    status = (
        "invalid_snapshot"
        if validation.snapshot_reasons
        else "evaluation_limited"
        if search_limited
        else "ready"
        if raw_path
        else "insufficient_coverage"
    )
    reasons = list(validation.snapshot_reasons)
    if objective_limited:
        reasons.append("diversity_optimization_budget_exhausted")
    if search_limited:
        reasons.append("search_budget_exhausted")
    elif not raw_path and not validation.snapshot_reasons:
        if len(accepted) < policy.rounds * 2:
            reasons.append("fewer_than_ten_eligible_candidates")
        try:
            unconstrained = find_path(all_tuple, min_categories=0, min_bands=0, _budget=budget)
        except SearchBudgetExceeded:
            unconstrained = None
            search_limited = True
            status = "evaluation_limited"
            reasons.append("search_budget_exhausted")
        if not search_limited:
            reasons.append("diversity_unmet" if unconstrained else "no_complete_no_repeat_path")
    path_categories = frozenset(c for pair in raw_path or () for c in pair.categories)
    path_bands = frozenset(pair.band for pair in raw_path or ())
    categories = frozenset(c for candidate in accepted for c in category_labels(candidate))
    evaluation = PoolEvaluation(
        policy.version,
        status,
        len(snapshot.candidates),
        len(accepted),
        len(snapshot.candidates) - len(accepted),
        validation.rejections,
        tuple(sorted(pair_rejections.items())),
        len(all_pairs),
        len(selected),
        snapshot.domain,
        snapshot.context_hash,
        len(categories),
        sum(not category_labels(c) for c in accepted),
        policy.min_categories,
        len(path_categories),
        tuple(sorted({p.band for p in all_pairs})),
        policy.min_bands,
        tuple(sorted(path_bands)),
        raw_path is not None,
        raw_path is not None,
        tuple(sorted(set(reasons))),
        policy.fingerprint,
        search_limited,
        objective_limited,
    )
    path_seed = f"{snapshot.context_hash}:{rng_seed}"
    return PoolBuildResult(
        status,
        tuple(selected),
        orient_path(raw_path, rng_seed=path_seed) if raw_path else (),
        evaluation,
        policy,
    )
