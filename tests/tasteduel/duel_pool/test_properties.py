"""Generated properties and adaptive continuation scenarios, entirely synthetic."""

from dataclasses import replace
import math
from random import Random

from tasteduel.domain.duel_pool import PairQualityPolicy, build_pool, continuation_options, find_path

from .oracle import is_disjoint_path
from .synthetic import candidate, snapshot
from .test_matching import edge
from .test_validation import assert_authoritative_pairs


def identity_winners(result):
    return {frozenset({pair.first.id, pair.second.id}): pair.winner_id for pair in result.pairs}


def test_rng_replay_and_winner_preservation_across_many_seeds():
    frozen = snapshot()
    known = {}
    for index in range(25):
        seed = f"private-reproducible-synthetic-{index}"
        result = build_pool(frozen, rng_seed=seed)
        assert result == build_pool(frozen, rng_seed=seed)
        assert result.status == "ready"
        for pair, winner in identity_winners(result).items():
            assert pair not in known or known[pair] == winner
            known[pair] = winner
        assert_authoritative_pairs(result)


def test_positive_score_rescaling_and_translation_do_not_create_cross_query_units():
    original = snapshot()
    base = build_pool(original, rng_seed="units")
    for scale, offset in ((2.0, 0.0), (0.25, 25.0), (1000.0, -10_000.0)):
        rows = tuple(replace(row, affinity=row.affinity * scale + offset) for row in original.candidates)
        result = build_pool(replace(original, candidates=rows), rng_seed="units")
        assert result.status == "ready"
        assert identity_winners(result) == identity_winners(base)
        assert tuple(pair.band for pair in result.pairs) == tuple(pair.band for pair in base.pairs)


def test_finite_extreme_scores_never_emit_nonfinite_engine_arithmetic():
    rows = tuple(candidate(index, affinity=1e308 * (1 - index / 10)) for index in range(20))
    assert all(math.isfinite(row.affinity) for row in rows)
    result = build_pool(snapshot(candidates=rows), rng_seed="large-finite")
    for pair in result.pairs:
        assert math.isfinite(pair.relative_gap)
        assert 0 < pair.relative_gap <= 1
    if result.status == "ready":
        assert is_disjoint_path((pair.left.entity.id, pair.right.entity.id) for pair in result.path)


def test_single_observed_gap_band_is_explicit_and_not_fabricated_into_three_bands():
    rows = tuple(candidate(index, affinity=1.0 if index < 5 else 0.0) for index in range(10))
    frozen = snapshot(candidates=rows)
    ordinary = build_pool(frozen, rng_seed="same-gap")
    requested = build_pool(frozen, rng_seed="same-gap", policy=PairQualityPolicy(min_bands=2))
    assert ordinary.status == "ready"
    assert len({pair.band for pair in ordinary.pairs}) == 1
    assert requested.status == "insufficient_coverage"
    assert not requested.path
    assert requested.evaluation.correction_reasons


def test_category_objective_is_feasible_on_actual_selected_path():
    result = build_pool(snapshot(), rng_seed="categories", policy=PairQualityPolicy(min_categories=4))
    assert result.status == "ready"
    path_ids = {pair.pair_id for pair in result.path}
    path = tuple(pair for pair in result.pairs if pair.id in path_ids)
    assert len(set().union(*(pair.categories for pair in path))) >= 4
    assert result.evaluation.categories_in_path >= 4


def test_every_exposed_continuation_option_preserves_full_path_and_diversity():
    pool = build_pool(
        snapshot(), rng_seed="adaptive", policy=PairQualityPolicy(min_categories=4, min_bands=2)
    )
    assert pool.status == "ready"
    rng = Random(713)
    for _ in range(15):
        used = frozenset()
        categories = frozenset()
        bands = frozenset()
        played = []
        for remaining in range(5, 0, -1):
            options = continuation_options(
                pool,
                used_entity_ids=used,
                rounds_remaining=remaining,
                seen_categories=categories,
                seen_bands=bands,
            )
            assert options
            for pair in options:
                assert not pair.entity_ids & used
                assert (
                    find_path(
                        pool.pairs,
                        rounds=remaining - 1,
                        used_entity_ids=used | pair.entity_ids,
                        min_categories=4,
                        min_bands=2,
                        seen_categories=categories | pair.categories,
                        seen_bands=bands | {pair.band},
                    )
                    is not None
                )
            chosen = rng.choice(options)
            played.append(chosen)
            used |= chosen.entity_ids
            categories |= chosen.categories
            bands |= {chosen.band}
        assert len(used) == 10 and len(categories) >= 4 and len(bands) >= 2
        assert is_disjoint_path((pair.first.id, pair.second.id) for pair in played)
    assert continuation_options(pool, rounds_remaining=0) == ()


def test_adaptive_options_reject_greedy_path_exhaustion():
    pool = build_pool(snapshot(), rng_seed="pool-for-graph")
    trap = edge(0, 1)
    edges = (trap, edge(0, 2), edge(1, 3), edge(4, 5), edge(6, 7), edge(8, 9))
    small = replace(pool, pairs=edges)
    options = continuation_options(small)
    assert trap.id not in {pair.id for pair in options}
    assert len(options) == 5


def test_previously_used_contestants_cannot_reenter_a_continuation():
    pool = build_pool(snapshot(), rng_seed="used")
    used = frozenset(row.id for row in snapshot().candidates)
    assert continuation_options(pool, used_entity_ids=used) == ()
