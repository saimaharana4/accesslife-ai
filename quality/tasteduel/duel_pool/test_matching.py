"""Exact feasibility compared with a small exhaustive, order-independent oracle."""

from dataclasses import replace
from itertools import combinations
from random import Random
from uuid import UUID

from tasteduel.domain.duel_pool import PrivatePair, find_path

from .oracle import disjoint_paths, is_disjoint_path
from .synthetic import candidate


def edge(left: int, right: int, *, band="medium", categories=frozenset()) -> PrivatePair:
    first, second = candidate(left), candidate(right)
    return PrivatePair(
        id=UUID(int=50_000 + min(left, right) * 100 + max(left, right)),
        first=first,
        second=second,
        winner_id=max((first, second), key=lambda item: item.affinity).id,
        band=band,
        relative_gap=0.5,
        categories=categories,
    )


def path_edges(path):
    return tuple((pair.first.id, pair.second.id) for pair in path)


def test_backtracking_finds_complete_path_despite_greedy_first_pair_trap():
    pairs = (edge(0, 1), edge(0, 2), edge(1, 3), edge(4, 5), edge(6, 7), edge(8, 9))
    path = find_path(pairs)
    assert path is not None
    assert is_disjoint_path(path_edges(path))
    assert pairs[0].id not in {item.id for item in path}


def test_five_individually_valid_star_edges_do_not_count_as_five_round_path():
    pairs = tuple(edge(0, index) for index in range(1, 6))
    assert len(pairs) == 5
    assert find_path(pairs) is None


def test_exact_feasibility_matches_independent_bruteforce_on_small_graphs():
    rng = Random(2031)
    all_edges = tuple(combinations(range(8), 2))
    for _ in range(100):
        chosen = rng.sample(all_edges, rng.randint(0, 12))
        pairs = tuple(edge(*vertices) for vertices in chosen)
        oracle = disjoint_paths(path_edges(pairs), count=3)
        actual = find_path(pairs, rounds=3)
        assert (actual is not None) == bool(oracle)
        if actual is not None:
            assert is_disjoint_path(path_edges(actual), count=3)
            assert frozenset(frozenset(item) for item in path_edges(actual)) in oracle


def test_matching_excludes_entities_that_were_already_delivered():
    pairs = tuple(edge(index, index + 1) for index in range(0, 12, 2))
    used = frozenset({candidate(0).id, candidate(1).id})
    path = find_path(pairs, rounds=5, used_entity_ids=used)
    assert path is not None
    assert not used.intersection(item for vertices in path_edges(path) for item in vertices)
    assert is_disjoint_path(path_edges(path))
    assert find_path(pairs[:5], rounds=5, used_entity_ids=used) is None


def test_diversity_must_exist_in_the_complete_path_not_merely_any_pool_edge():
    repeated = tuple(edge(0, index, categories=frozenset({"rare"})) for index in range(1, 6))
    disjoint = tuple(edge(index, index + 1, categories=frozenset({"common"})) for index in range(0, 10, 2))
    pairs = repeated + disjoint
    path = find_path(pairs, min_categories=2)
    assert path is not None
    assert is_disjoint_path(path_edges(path))
    assert len(set().union(*(pair.categories for pair in path))) >= 2
    # The sole rare edge cannot be used if its shared contestant has already appeared.
    assert find_path(pairs, used_entity_ids=frozenset({candidate(0).id}), min_categories=2) is None


def test_requested_band_diversity_does_not_silently_relax_for_single_band_pool():
    pairs = tuple(edge(index, index + 1, band="hard") for index in range(0, 10, 2))
    assert find_path(pairs, min_bands=1) is not None
    assert find_path(pairs, min_bands=2) is None
    assert find_path(pairs, min_bands=2, seen_bands=frozenset({"easy"})) is not None


def test_seen_categories_count_toward_continuation_without_reusing_contestants():
    pairs = tuple(edge(index, index + 1, categories=frozenset({"common"})) for index in range(0, 8, 2))
    assert find_path(pairs, rounds=4, min_categories=2) is None
    assert find_path(pairs, rounds=4, min_categories=2, seen_categories=frozenset({"earlier"})) is not None


def test_required_band_and_category_sets_are_joint_constraints():
    base = tuple(edge(index, index + 1, categories=frozenset({"one"})) for index in range(0, 10, 2))
    rare = replace(base[0], band="easy", categories=frozenset({"two"}))
    assert find_path((rare,) + base[1:], min_categories=2, min_bands=2) is not None
