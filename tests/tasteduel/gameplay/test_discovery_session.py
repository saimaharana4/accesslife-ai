"""Explicit save signals and guest revocation exercise actual PostgreSQL authority."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
import time
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update

from tasteduel.persistence import models as m
from tasteduel.persistence.db import scoped_session

from .test_authoritative_flow import answer_body, create, next_body, post


def start(gameplay, owned_seed):
    client, owner, curator = gameplay()
    body = owned_seed(owner)
    response = create(client, body)
    assert response.status_code == 201
    game = response.json()
    return client, owner, curator, body, game


def accept(client, game):
    response = post(
        client,
        f"/v1/games/{game['game_id']}/answer",
        answer_body(game["current_round"]),
        "discovery-answer-key-0001",
    )
    assert response.status_code == 200
    return response.json()


def save(client, entity_id, key="discovery-save-key-0001"):
    return post(client, "/v1/discoveries", {"entity_id": entity_id}, key)


def test_empty_collection_reports_session_expiry(gameplay):
    client, _, _ = gameplay()
    result = client.get("/v1/discoveries")
    assert result.status_code == 200
    assert result.json()["discoveries"] == []
    assert result.json()["expired_count"] == 0
    assert result.json()["session_expires_at"] == client.get("/v1/sessions/current").json()["expires_at"]


def test_unanswered_seed_future_unknown_and_foreign_entities_cannot_be_saved(gameplay, owned_seed, db_engine):
    client, owner, _, body, game = start(gameplay, owned_seed)
    visible = game["current_round"]["choices"][0]["entity"]["id"]
    with scoped_session(db_engine, owner) as db:
        future = db.scalar(
            select(m.Entity.id).where(
                m.Entity.session_id == owner,
                m.Entity.entity_type == "movie",
                m.Entity.id.not_in([UUID(c["entity"]["id"]) for c in game["current_round"]["choices"]]),
            )
        )
    foreign, foreign_owner, _ = gameplay()
    foreign_seed = owned_seed(foreign_owner)
    for index, entity in enumerate(
        (visible, body["seed_entity_id"], str(future), str(uuid4()), foreign_seed["seed_entity_id"])
    ):
        assert save(client, entity, f"discovery-denied-key-{index:04d}").status_code == 404
    assert foreign.get("/v1/discoveries").json()["discoveries"] == []


@pytest.mark.parametrize("correct", [True, False])
def test_prediction_correctness_never_creates_a_preference_or_discovery(
    gameplay, owned_seed, db_engine, correct
):
    client, owner, curator, _, game = start(gameplay, owned_seed)
    current = game["current_round"]
    with scoped_session(db_engine, owner) as db:
        winner = db.scalar(
            select(m.PrivatePair.winner_entity_id)
            .join(m.DeliveredRound, m.DeliveredRound.pair_id == m.PrivatePair.id)
            .where(m.DeliveredRound.id == UUID(current["round_id"]))
        )
    chosen = next(
        choice for choice in current["choices"] if (UUID(choice["entity"]["id"]) == winner) == correct
    )
    body = {**answer_body(current), "choice_id": chosen["id"]}
    answered = post(client, f"/v1/games/{game['game_id']}/answer", body, "prediction-only-key-0001")
    assert answered.status_code == 200 and answered.json()["correct"] is correct
    assert client.get("/v1/discoveries").json()["discoveries"] == []
    with scoped_session(db_engine, owner) as db:
        assert db.scalar(select(func.count()).select_from(m.Discovery)) == 0
        assert (
            db.scalar(
                select(func.count())
                .select_from(m.MutationReceipt)
                .where(m.MutationReceipt.operation == "save_discovery")
            )
            == 0
        )
    # Either revealed contestant can be explicitly selected, independent of correctness.
    for index, choice in enumerate(current["choices"]):
        saved = save(client, choice["entity"]["id"], f"explicit-discovery-key-{index:04d}")
        assert saved.status_code == 201
        assert saved.json()["entity"] == choice["entity"]
        assert "correct" not in saved.json() and "preference" not in saved.json()
    assert curator.calls == 1


def test_save_retry_conflict_unsave_and_explicit_resave(gameplay, owned_seed, db_engine):
    client, owner, _, _, game = start(gameplay, owned_seed)
    reveal = accept(client, game)
    first, second = [choice["entity"]["id"] for choice in reveal["choices"]]
    saved = save(client, first)
    assert saved.status_code == 201
    assert save(client, first).status_code == 200
    assert save(client, first).json() == saved.json()
    conflict = save(client, second)
    assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert client.delete(f"/v1/discoveries/{first}").status_code == 204
    assert client.delete(f"/v1/discoveries/{first}").status_code == 204
    assert client.get("/v1/discoveries").json()["discoveries"] == []
    removed = save(client, first)
    assert removed.status_code == 409 and removed.json()["error"]["code"] == "DISCOVERY_REMOVED"
    assert save(client, first, "explicit-resave-key-0002").status_code == 201
    # An old uncertain save remains superseded even after a new explicit save.
    assert save(client, first).status_code == 409
    with scoped_session(db_engine, owner) as db:
        assert db.scalar(select(func.count()).select_from(m.Discovery)) == 1
        assert db.scalar(select(func.count()).select_from(m.Answer)) == 1


def test_two_tabs_concurrent_save_retry_has_one_signal(gameplay, owned_seed, db_engine):
    client, owner, curator, _, game = start(gameplay, owned_seed)
    reveal = accept(client, game)
    entity = reveal["choices"][0]["entity"]["id"]
    other, _, _ = gameplay(cookie=client.cookies.get("tasteduel_session"))
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda browser: save(browser, entity), (client, other)))
    assert sorted(result.status_code for result in results) == [200, 201]
    assert results[0].json() == results[1].json()
    with scoped_session(db_engine, owner) as db:
        assert db.scalar(select(func.count()).select_from(m.Discovery)) == 1
        assert (
            db.scalar(
                select(func.count())
                .select_from(m.MutationReceipt)
                .where(m.MutationReceipt.operation == "save_discovery")
            )
            == 1
        )
    assert curator.calls == 1


def test_save_survives_api_restart_and_foreign_unsave_is_noop(gameplay, owned_seed):
    client, _, _, _, game = start(gameplay, owned_seed)
    reveal = accept(client, game)
    entity = reveal["choices"][0]["entity"]["id"]
    saved = save(client, entity)
    cookie = client.cookies.get("tasteduel_session")
    restarted, _, curator = gameplay(cookie=cookie)
    assert restarted.get("/v1/discoveries").json()["discoveries"] == [saved.json()]
    assert save(restarted, entity).json() == saved.json()
    stranger, _, _ = gameplay()
    assert stranger.get("/v1/discoveries").json()["discoveries"] == []
    assert stranger.delete(f"/v1/discoveries/{entity}").status_code == 204
    assert len(restarted.get("/v1/discoveries").json()["discoveries"]) == 1
    assert save(stranger, entity).status_code == 404
    assert curator.calls == 0


def test_expired_game_hides_discovery_metadata_without_rewriting_answer(gameplay, owned_seed, db_engine):
    client, owner, _, _, game = start(gameplay, owned_seed)
    reveal = accept(client, game)
    entity = reveal["choices"][0]["entity"]["id"]
    assert save(client, entity).status_code == 201
    with scoped_session(db_engine, owner) as db:
        db.execute(
            update(m.Game)
            .where(m.Game.id == UUID(game["game_id"]))
            .values(
                expires_at=datetime.now(UTC) + timedelta(milliseconds=60),
                revision=m.Game.revision + 1,
            )
        )
        answers = [(row.id, row.choice_id, row.correct) for row in db.scalars(select(m.Answer))]
    time.sleep(0.09)
    result = client.get("/v1/discoveries").json()
    assert result["discoveries"] == [] and result["expired_count"] == 1
    assert reveal["choices"][0]["entity"]["name"] not in str(result)
    assert save(client, entity, "expired-discovery-key-002").status_code == 410
    with scoped_session(db_engine, owner) as db:
        assert [(row.id, row.choice_id, row.correct) for row in db.scalars(select(m.Answer))] == answers
    assert client.delete(f"/v1/discoveries/{entity}").status_code == 204
    assert client.get("/v1/discoveries").json()["expired_count"] == 0


def test_clear_revokes_other_tab_and_api_restart_private_access(gameplay, owned_seed, db_engine):
    client, owner, _, _, game = start(gameplay, owned_seed)
    reveal = accept(client, game)
    entity = reveal["choices"][0]["entity"]["id"]
    assert save(client, entity).status_code == 201
    cookie = client.cookies.get("tasteduel_session")
    other, _, _ = gameplay(cookie=cookie)
    assert client.delete("/v1/sessions/current").status_code == 204
    restarted, _, _ = gameplay(cookie=cookie)
    for browser in (other, restarted):
        for path in ("/v1/sessions/current", "/v1/discoveries", f"/v1/games/{game['game_id']}"):
            assert browser.get(path).status_code == 401
        assert save(browser, entity).status_code == 401
        assert browser.delete(f"/v1/discoveries/{entity}").status_code == 401
    # Revocation, rather than deletion, invalidates all old capabilities.
    with scoped_session(db_engine, owner) as db:
        session = db.get(m.Session, owner)
        assert session.revoked_at is not None
    assert client.delete("/v1/sessions/current").status_code == 204
    assert client.post("/v1/sessions", json={}).status_code == 201
    assert client.get("/v1/discoveries").json()["discoveries"] == []


def test_clearing_completed_source_revokes_existing_frozen_challenge(gameplay, owned_seed, db_engine):
    client, owner, _, _, game = start(gameplay, owned_seed)
    identifier = game["game_id"]
    for ordinal in range(1, 6):
        current = client.get(f"/v1/games/{identifier}").json()["current_round"]
        reveal = post(
            client, f"/v1/games/{identifier}/answer", answer_body(current), f"source-answer-key-{ordinal:04d}"
        ).json()
        assert (
            post(
                client,
                f"/v1/games/{identifier}/advance",
                next_body(reveal),
                f"source-advance-key-{ordinal:04d}",
            ).status_code
            == 200
        )
    with scoped_session(db_engine, owner) as db:
        source = db.get(m.Game, UUID(identifier))
        result = db.scalar(select(m.GameResult).where(m.GameResult.game_id == source.id))
        challenge = m.Challenge(
            id=uuid4(),
            session_id=owner,
            source_game_id=source.id,
            slug_hash=uuid4().hex * 2,
            version=1,
            creator_score=result.score,
            scoring_version=source.scoring_version,
            validator_version=source.validator_version,
            expires_at=source.expires_at,
        )
        db.add(challenge)
        db.flush()
        challenge_id = challenge.id
    # Observe inside the same transaction immediately before revocation hides
    # rows through FORCE RLS. The real statement/trigger must revoke the share.
    from sqlalchemy import event

    observed = []

    def inspect_revocation(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().startswith("UPDATE tasteduel.challenges"):
            cursor.execute(
                "SELECT revoked_at IS NOT NULL FROM tasteduel.challenges WHERE id=%s", (challenge_id,)
            )
            observed.append(cursor.fetchone()[0])

    event.listen(db_engine, "after_cursor_execute", inspect_revocation)
    try:
        assert client.delete("/v1/sessions/current").status_code == 204
    finally:
        event.remove(db_engine, "after_cursor_execute", inspect_revocation)
    assert observed == [True]
