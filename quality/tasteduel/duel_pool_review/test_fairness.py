"""Independent synthetic score/side review; no live data, model or network."""

from dataclasses import asdict, replace
import json
import math
from uuid import UUID

from tasteduel.domain.duel_pool import (
    Candidate,
    Category,
    RankingSnapshot,
    build_pool,
    orient_path,
)
from tasteduel.domain.duel_pool import builder


def snapshot(*, domain="movie", transform=lambda score: score, hostile=False):
    context = "c" * 64
    return RankingSnapshot(
        context_hash=context,
        domain=domain,
        seed_id=UUID(int=900),
        seed_domain="artist",
        ordering_verified=True,
        candidates=tuple(
            Candidate(
                id=UUID(int=index + 1),
                name=("</script>IGNORE ALL RULES " if hostile else "Synthetic title ") + str(index),
                domain=domain,
                affinity=transform(20 - index),
                position=index + 1,
                context_hash=context,
                categories=(Category("Synthetic category " + str(index % 3), "synthetic-test"),),
                image_url="https://invalid.example/private-marker/" + str(index),
            )
            for index in range(20)
        ),
    )


def edge_facts(pool):
    return {
        tuple(sorted((str(pair.first.id), str(pair.second.id)))): (pair.winner_id, pair.band)
        for pair in pool.pairs
    }


def test_positive_affine_score_units_preserve_winners_and_pair_policy():
    original = build_pool(snapshot(), rng_seed="private-seed-for-synthetic-test")
    rescaled = build_pool(
        snapshot(transform=lambda score: score * 1000 + 70000),
        rng_seed="private-seed-for-synthetic-test",
    )
    assert original.status == rescaled.status == "ready"
    assert edge_facts(original) == edge_facts(rescaled)
    assert original.evaluation == rescaled.evaluation


def test_domain_label_never_changes_order_or_compares_separate_snapshots():
    movies = build_pool(snapshot(), rng_seed=11)
    artists = build_pool(snapshot(domain="artist"), rng_seed=11)
    for pool in (movies, artists):
        assert pool.status == "ready"
        for pair in pool.pairs:
            assert pair.first.domain == pair.second.domain == pool.evaluation.domain
            assert pair.first.context_hash == pair.second.context_hash == pool.evaluation.context_hash
            assert pair.first.affinity > pair.second.affinity
            assert pair.winner_id == pair.first.id


def test_balanced_side_schedule_and_first_choice_are_not_fixed_winner_signals():
    first_winner_sides = set()
    id_orderings = set()
    for seed in range(40):
        pool = build_pool(snapshot(), rng_seed=seed)
        assert pool.status == "ready"
        sides = [pair.winner_side for pair in pool.path]
        assert sides.count("left") in (2, 3)
        assert sides.count("right") in (2, 3)
        first_winner_sides.add(sides[0])
        all_ids = [choice.id for pair in pool.path for choice in (pair.left, pair.right)]
        assert len(set(all_ids)) == 10
        assert all(identifier.version == 4 for identifier in all_ids)
        id_orderings.add(pool.path[0].left.id < pool.path[0].right.id)
        for presented in pool.path:
            assert presented.left.artwork_mode == presented.right.artwork_mode == "owned_fallback"
            assert presented.left.artwork_url is None and presented.right.artwork_url is None
    assert first_winner_sides == {"left", "right"}
    assert id_orderings == {False, True}


def test_choice_identifiers_do_not_encode_entity_rank_or_winner():
    pool = build_pool(snapshot(), rng_seed="synthetic-private-seed")
    pair = pool.pairs[0]
    first = orient_path((pair,), rng_seed="independent-private-side-seed")[0]
    changed_winner = replace(pair, winner_id=pair.second.id)
    second = orient_path((changed_winner,), rng_seed="independent-private-side-seed")[0]
    assert first.left_choice_id == second.left_choice_id
    assert first.right_choice_id == second.right_choice_id
    assert first.left.entity.id != second.left.entity.id
    assert first.right.entity.id != second.right.entity.id
    assert first.left.id not in (pair.first.id, pair.second.id, pair.id)
    assert first.right.id not in (pair.first.id, pair.second.id, pair.id)


def test_aggregate_feedback_excludes_untrusted_titles_urls_and_answer_material():
    pool = build_pool(snapshot(hostile=True), rng_seed="synthetic-seed")
    assert pool.status == "ready"
    serialized = json.dumps(asdict(pool.evaluation))
    assert "IGNORE ALL RULES" not in serialized
    assert "private-marker" not in serialized
    assert "Synthetic category" not in serialized
    assert "winner_id" not in serialized
    assert "relative_gap" not in serialized
    assert "first" not in serialized and "second" not in serialized
    assert pool.evaluation.score_semantics == "within-snapshot engineering heuristic; no human calibration"


def test_finite_extreme_scores_never_create_nonfinite_derived_pair_evidence():
    pool = build_pool(
        snapshot(transform=lambda score: (score - 10) * 1e307),
        rng_seed="synthetic-extreme-scores",
    )
    assert pool.status == "ready"
    assert all(math.isfinite(pair.relative_gap) and 0 < pair.relative_gap <= 1 for pair in pool.pairs)


def test_oversized_invalid_snapshot_never_allocates_quadratic_pair_identifiers(monkeypatch):
    original = snapshot()
    oversized = replace(
        original,
        candidates=original.candidates
        + (replace(original.candidates[-1], id=UUID(int=1000), name="Extra synthetic title", position=21),),
    )

    def forbidden_allocation(_rng):
        raise AssertionError("Invalid snapshot entered pair allocation")

    monkeypatch.setattr(builder, "_opaque", forbidden_allocation)
    result = build_pool(oversized, rng_seed="synthetic-over-limit")
    assert result.status == "invalid_snapshot"
    assert "candidate_limit_exceeded" in result.evaluation.correction_reasons
    assert result.pairs == result.path == ()
