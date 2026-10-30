"""Invented identifiers and metadata, never Qloo response captures."""

from uuid import UUID

from tasteduel.domain.duel_pool import Candidate, Category, RankingSnapshot

CONTEXT = "synthetic-context-one"
SEED_ID = UUID(int=999)


def candidate(index: int, **changes) -> Candidate:
    values = {
        "id": UUID(int=1000 + index),
        "name": f"Synthetic Movie {index:02d}",
        "domain": "movie",
        "affinity": float(100 - 5 * index),
        "position": index + 1,
        "context_hash": CONTEXT,
        "categories": (Category(label=f"Synthetic category {index % 4}", source="synthetic"),),
    }
    values.update(changes)
    return Candidate(**values)


def snapshot(count: int = 20, *, candidates=None, **changes) -> RankingSnapshot:
    values = {
        "context_hash": CONTEXT,
        "domain": "movie",
        "seed_id": SEED_ID,
        "seed_domain": "artist",
        "candidates": tuple(candidate(index) for index in range(count)) if candidates is None else candidates,
        "ordering_verified": True,
    }
    values.update(changes)
    return RankingSnapshot(**values)
