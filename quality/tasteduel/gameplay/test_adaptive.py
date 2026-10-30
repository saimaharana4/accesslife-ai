"""Prediction-performance selection; synthetic graph, real PostgreSQL authority."""

from itertools import product
from uuid import UUID

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError

from tasteduel.domain.adaptive import (
    SELECTION_VERSION,
    InsufficientContinuation,
    PerformanceRound,
    SelectionPair,
    choose_next,
)
from tasteduel.persistence import models as m
from tasteduel.persistence.db import scoped_session

from .test_authoritative_flow import create, game, next_body, post


def edge(index, band, *, entities=None, categories=()):
    return SelectionPair(
        UUID(int=100 + index),
        frozenset(UUID(int=value) for value in (entities or (index * 2 + 1, index * 2 + 2))),
        band,
        frozenset(categories),
    )


def rich_pool():
    return tuple(edge(index, band) for index, band in enumerate(("easy", "medium", "hard") * 5))


def choose(pairs, history=(), *, seed=bytes(32), **kwargs):
    return choose_next(pairs, history, selection_seed=seed, **kwargs)


def played(pairs, selection, correct=True):
    return PerformanceRound(
        next(pair for pair in pairs if pair.id == selection.pair_id), correct, selection.winner_side
    )


def test_medium_start_two_real_predictions_raise_then_miss_eases():
    pairs = rich_pool()
    history = ()
    expected = (("medium", True), ("medium", True), ("hard", False), ("medium", False), ("easy", True))
    for band, correct in expected:
        selection = choose(pairs, history)
        assert selection.requested_band == selection.selected_band == band
        history += (played(pairs, selection, correct),)


@pytest.mark.parametrize("outcomes", list(product((False, True), repeat=5)))
def test_all_prediction_patterns_finish_without_repeats_and_preserve_pool(outcomes):
    pairs = rich_pool()
    original = tuple(pairs)
    for value in range(4):
        history = ()
        used = set()
        for correct in outcomes:
            selection = choose(pairs, history, seed=bytes([value]) * 32)
            row = played(pairs, selection, correct)
            assert not row.pair.entities & used
            used.update(row.pair.entities)
            history += (row,)
    assert pairs == original


def test_scarce_band_explicit_and_deterministic_permutation_independence():
    pairs = tuple(edge(index, "easy") for index in range(5))
    first = choose(pairs)
    assert first.requested_band == "medium" and first.selected_band == "easy"
    assert first.reason == "scarce_feasible_band"
    assert first == choose(tuple(reversed(pairs)))


def test_preferred_band_cannot_exhaust_complete_path_or_diversity():
    pairs = (
        edge(0, "medium", entities=(1, 3)),
        edge(1, "easy", entities=(1, 2), categories=("required",)),
        edge(2, "easy", entities=(3, 4)),
        edge(3, "easy", entities=(5, 6)),
        edge(4, "easy", entities=(7, 8)),
        edge(5, "easy", entities=(9, 10)),
    )
    selected = choose(pairs, min_categories=1)
    assert selected.pair_id != pairs[0].id
    assert selected.reason == "scarce_feasible_band"
    with pytest.raises(InsufficientContinuation):
        choose(pairs, min_categories=2)


def test_tiny_pool_and_duplicated_history_rejected():
    pairs = rich_pool()
    with pytest.raises(InsufficientContinuation):
        choose(pairs[:4])
    first = played(pairs, choose(pairs))
    with pytest.raises(ValueError, match="history"):
        choose(pairs, (first, first))
    with pytest.raises(ValueError, match="private"):
        choose(pairs, seed=b"public-id")


def test_private_seed_changes_first_side_and_does_not_force_alternation():
    pairs = rich_pool()
    first_sides, schedules = set(), set()
    for number in range(256):
        history = ()
        for _ in range(5):
            selected = choose(pairs, history, seed=number.to_bytes(32))
            history += (played(pairs, selected),)
        first_sides.add(history[0].winner_side)
        schedules.add(tuple(row.winner_side for row in history))
    assert first_sides == {"left", "right"}
    assert any(sides[0] == sides[1] for sides in schedules)
    assert len(schedules) == 32
    for prefix in product(("left", "right"), repeat=4):
        assert {sides[4] for sides in schedules if sides[:4] == prefix} == {"left", "right"}


def test_adaptive_database_rounds_retries_restart_and_never_create_preferences(
    gameplay, owned_seed, db_engine
):
    client, owner, curator = gameplay()
    response = create(client, owned_seed(owner))
    assert response.status_code == 201
    identifier = response.json()["game_id"]
    with scoped_session(db_engine, owner) as db:
        stored_game = db.get(m.Game, UUID(identifier))
        assert stored_game.selection_version == SELECTION_VERSION and len(stored_game.selection_seed) == 64
        winners = {
            row.id: row.winner_entity_id
            for row in db.scalars(select(m.PrivatePair).where(m.PrivatePair.game_id == UUID(identifier)))
        }
    score, used, sides = 0, set(), []
    for ordinal in range(1, 6):
        current = game(client, identifier)["current_round"]
        with scoped_session(db_engine, owner) as db:
            delivered = db.get(m.DeliveredRound, UUID(current["round_id"]))
            context = dict(delivered.selection_context)
            assert context["policy_version"] == SELECTION_VERSION
            sides.append(context["winner_side"])
            winner = winners[delivered.pair_id]
        assert "selection_context" not in current and "selection_seed" not in current
        chosen = next(
            choice
            for choice in current["choices"]
            if (UUID(choice["entity"]["id"]) == winner) == (ordinal != 3)
        )
        for choice in current["choices"]:
            assert choice["entity"]["id"] not in used
            used.add(choice["entity"]["id"])
        body = {
            "round_id": current["round_id"],
            "choice_id": chosen["id"],
            "expected_revision": current["revision"],
        }
        answered = post(client, f"/v1/games/{identifier}/answer", body, f"adaptive-answer-{ordinal:04d}")
        assert answered.status_code == 200
        reveal = answered.json()
        score += ordinal != 3
        assert reveal["cumulative_score"] == score
        assert (
            post(client, f"/v1/games/{identifier}/answer", body, f"adaptive-answer-{ordinal:04d}").json()
            == reveal
        )
        if ordinal == 2:
            cookie = client.cookies.get("tasteduel_session")
            client, _, restarted = gameplay(cookie=cookie)
            assert game(client, identifier)["current_round"] == reveal and restarted.calls == 0
        advanced = post(
            client, f"/v1/games/{identifier}/advance", next_body(reveal), f"adaptive-advance-{ordinal:04d}"
        )
        assert advanced.status_code == 200
        assert (
            post(
                client,
                f"/v1/games/{identifier}/advance",
                next_body(reveal),
                f"adaptive-advance-{ordinal:04d}",
            ).json()
            == advanced.json()
        )
    assert len(sides) == 5 and set(sides) <= {"left", "right"}
    assert curator.calls == 1
    assert client.get(f"/v1/games/{identifier}/results").json()["score"] == 4
    with scoped_session(db_engine, owner) as db:
        assert winners == {
            row.id: row.winner_entity_id
            for row in db.scalars(select(m.PrivatePair).where(m.PrivatePair.game_id == UUID(identifier)))
        }
        assert (
            db.scalar(select(func.count()).select_from(m.Discovery).where(m.Discovery.session_id == owner))
            == 0
        )


def test_database_freezes_private_selection_policy_and_orientation(gameplay, owned_seed, db_engine):
    client, owner, _ = gameplay()
    identifier = UUID(create(client, owned_seed(owner)).json()["game_id"])
    with pytest.raises(DBAPIError) as rejected:
        with scoped_session(db_engine, owner) as db:
            stored = db.get(m.Game, identifier)
            db.execute(
                update(m.Game)
                .where(m.Game.id == identifier)
                .values(selection_seed="f" * 64, revision=stored.revision + 1)
            )
    assert rejected.value.orig.sqlstate == "23514"
    with scoped_session(db_engine, owner) as db:
        delivered = db.scalar(select(m.DeliveredRound).where(m.DeliveredRound.game_id == identifier))
        assert delivered.left_entity_id != delivered.right_entity_id
        assert delivered.selection_context["policy_version"] == SELECTION_VERSION
        round_id = delivered.id
    with pytest.raises(DBAPIError) as rejected:
        with scoped_session(db_engine, owner) as db:
            db.execute(
                update(m.DeliveredRound)
                .where(m.DeliveredRound.id == round_id)
                .values(selection_context={"policy_version": "rewritten"})
            )
    # Runtime cannot mutate delivered records; migration-owner is not used.
    assert rejected.value.orig.sqlstate == "42501"
