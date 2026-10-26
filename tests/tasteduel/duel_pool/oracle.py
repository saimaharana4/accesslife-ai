"""Small exhaustive oracle, deliberately independent of production search order."""

from itertools import combinations
from typing import Hashable, Iterable


def disjoint_paths(
    edges: Iterable[tuple[Hashable, Hashable]], count: int
) -> set[frozenset[frozenset[Hashable]]]:
    """Enumerate all matchings on small synthetic graphs, ignoring edge orientation."""
    unique = tuple({frozenset(edge) for edge in edges if edge[0] != edge[1]})
    return {
        frozenset(chosen) for chosen in combinations(unique, count) if len(set().union(*chosen)) == count * 2
    }


def is_disjoint_path(edges: Iterable[tuple[Hashable, Hashable]], count: int = 5) -> bool:
    values = tuple(edges)
    return len(values) == count and len({item for edge in values for item in edge}) == 2 * count
