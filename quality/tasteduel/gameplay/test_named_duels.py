"""Named guests, participant-only verdicts and physical lifecycle cleanup."""

from datetime import UTC, datetime, timedelta
import hashlib
import secrets
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text

from tasteduel import operations
from tasteduel.persistence import models as m
from tasteduel.persistence.db import scoped_session

from .test_authoritative_flow import create, post
from .test_challenges import complete, shared


def test_atomic_named_bootstrap_retries_and_duplicate_names(gameplay):
    client, _, _ = gameplay()
    client.cookies.clear()
    key = secrets.token_urlsafe(32)
    first = client.post("/v1/sessions", json={"display_name": "  Mira   Moon "}, headers={"Idempotency-Key": key})
    assert first.status_code == 201
    token = client.cookies.get("tasteduel_session")
    assert first.json()["display_name"] == "Mira Moon"
    client.cookies.clear()  # Simulate losing the first response, including Set-Cookie.
    retry = client.post("/v1/sessions", json={"display_name": "Mira Moon"}, headers={"Idempotency-Key": key})
    assert retry.status_code == 200 and client.cookies.get("tasteduel_session") == token
    assert client.post("/v1/sessions/name", json={"display_name": "Someone else"}).status_code == 409
    other, _, _ = gameplay()
    other.cookies.clear()
    assert other.post("/v1/sessions", json={"display_name": "Mira Moon"}).status_code == 201
    assert other.cookies.get("tasteduel_session") != token


@pytest.mark.parametrize("name", ["", "   ", "x" * 25, "<script>", "abc\u202edef", "a\x00b", 123])
def test_invalid_nicknames_do_not_create_sessions(gameplay, name):
    client, _, _ = gameplay()
    client.cookies.clear()
    response = client.post("/v1/sessions", json={"display_name": name})
    assert response.status_code == 422
    assert "tasteduel_session" not in client.cookies
    assert "input" not in str(response.json())


def test_named_verdict_retries_replays_and_isolation(gameplay, owned_seed, db_engine):
    creator, owner, curator, source, reveals, invitation = shared(gameplay, owned_seed)
    assert creator.post("/v1/sessions/name", json={"display_name": "Mira"}).status_code == 200
    slug = invitation["invitation"]["slug"]
    assert creator.get(f"/v1/challenges/{slug}").json()["creator_name"] == "Mira"
    assert post(creator, f"/v1/challenges/{slug}/plays", {}, "self-poke-000000001").status_code == 409
    friend, guest, unused = gameplay()
    friend.post("/v1/sessions/name", json={"display_name": "Rio"})
    replay = post(friend, f"/v1/challenges/{slug}/plays", {}, "named-play-000000001").json()
    # New tabs and different retry identities still resume the active attempt.
    assert post(friend, f"/v1/challenges/{slug}/plays", {}, "named-play-000000002").json()["game_id"] == replay["game_id"]
    replay, _ = complete(friend, replay, choose_winner=True, expected=reveals)
    url = f"/v1/games/{source['game_id']}/duels"
    creator_result = creator.get(url)
    assert creator_result.status_code == 200, creator_result.json()
    outcome = creator_result.json()["outcomes"][0]
    assert outcome["creator_name"] == "Mira" and outcome["challenger_name"] == "Rio"
    assert outcome["challenger_score"] == 5 and outcome["attempt_number"] == 1
    assert outcome["outcome"] == ("tie" if source["score"] == 5 else "challenger")
    assert not {"session_id", "game_id", "winning_choice_id", "answers"}.intersection(outcome)
    assert friend.get(url).status_code == 404
    stranger, _, _ = gameplay()
    assert stranger.get(f"/v1/games/{replay['game_id']}/duels").status_code == 404
    assert friend.get(f"/v1/games/{replay['game_id']}/duels").json()["outcomes"] == [outcome]
    second = post(friend, f"/v1/challenges/{slug}/plays", {"new_attempt": True}, "named-play-again-00001")
    assert second.status_code == 201
    assert second.json()["game_id"] != replay["game_id"]
    assert post(friend, f"/v1/challenges/{slug}/plays", {"new_attempt": True}, "named-play-again-00001").status_code == 200
    with scoped_session(db_engine, guest) as db:
        assert list(db.scalars(select(m.ChallengePlay.attempt_number).order_by(m.ChallengePlay.attempt_number))) == [1, 2]
    assert curator.calls == 1 and unused.calls == 0
    assert creator.delete(f"/v1/challenges/{slug}").status_code == 204
    assert creator.get(url).json()["status"] == "retired"
    assert friend.get(f"/v1/games/{replay['game_id']}/duels").status_code == 410


def test_polling_does_not_touch_activity_and_completion_has_ten_minutes(gameplay, owned_seed, db_engine):
    creator, owner, _, source, reveals, invitation = shared(gameplay, owned_seed)
    friend, guest, _ = gameplay()
    slug = invitation["invitation"]["slug"]
    replay = post(friend, f"/v1/challenges/{slug}/plays", {}, "deadline-play-00000001").json()
    complete(friend, replay, expected=reveals)
    with scoped_session(db_engine, owner) as db:
        before = db.get(m.Session, owner).last_activity_at
        deadline = db.scalar(text("SELECT tasteduel.challenge_deadline(id) FROM tasteduel.challenges WHERE share_slug=:slug"), {"slug": slug})
    assert timedelta(minutes=9) < deadline-datetime.now(UTC) <= timedelta(minutes=10)
    for _ in range(3):
        assert creator.get(f"/v1/games/{source['game_id']}/duels").status_code == 200
        assert creator.get("/v1/sessions/current").status_code == 200
    with scoped_session(db_engine, owner) as db:
        assert db.get(m.Session, owner).last_activity_at == before


def test_idle_guest_is_denied_and_physically_purged(gameplay, db_engine, db_owner_engine):
    active, active_owner, _ = gameplay()
    now = datetime.now(UTC)
    owner = uuid4()
    token = f"{owner}.{secrets.token_urlsafe(32)}"
    with scoped_session(db_engine, owner) as db:
        db.add(m.Session(id=owner, display_name="Expired nickname", token_hash=hashlib.sha256(token.encode()).hexdigest(),
            created_at=now-timedelta(hours=2), last_activity_at=now-timedelta(hours=2), expires_at=now+timedelta(hours=20)))
    idle, _, _ = gameplay(cookie=token)
    assert idle.get("/v1/sessions/current").status_code == 401
    with db_owner_engine.begin() as db:
        for _ in range(3):
            operations.purge(db, execute=True)
        assert db.execute(text("SELECT count(*) FROM tasteduel.sessions WHERE id=:id"), {"id": owner}).scalar_one() == 0
    assert active.get("/v1/sessions/current").status_code == 200
    with scoped_session(db_engine, active_owner) as db:
        assert db.get(m.Session, active_owner) is not None


def test_active_friend_protects_idle_source(gameplay, owned_seed, db_engine, db_owner_engine):
    creator, owner, _, source, _, invitation = shared(gameplay, owned_seed)
    friend, _, _ = gameplay()
    replay = post(friend, f"/v1/challenges/{invitation['invitation']['slug']}/plays", {}, "protect-play-00000001")
    assert replay.status_code == 201
    # Age only the synthetic creator clock. Roll back this test-only DDL and
    # update together; production guards are never disabled or weakened.
    with db_owner_engine.connect() as db:
        transaction = db.begin()
        try:
            db.execute(text("ALTER TABLE tasteduel.sessions DISABLE TRIGGER guard_session_update"))
            db.execute(text("SELECT set_config('app.session_id',:id,true)"), {"id": str(owner)})
            db.execute(text("UPDATE tasteduel.sessions SET last_activity_at=clock_timestamp()-interval '2 hours' WHERE id=:id"), {"id": owner})
            assert db.execute(text("SELECT tasteduel.session_live(:id)"), {"id": owner}).scalar_one()
            operations.purge(db, execute=True)
            assert db.execute(text("SELECT count(*) FROM tasteduel.games WHERE id=:id"), {"id": UUID(source["game_id"])}).scalar_one() == 1
        finally:
            transaction.rollback()


def test_completion_cleanup_removes_graph_without_touching_active_game(gameplay, owned_seed, db_owner_engine):
    creator, owner, _, source, reveals, invitation = shared(gameplay, owned_seed)
    friend, _, _ = gameplay()
    replay = post(friend, f"/v1/challenges/{invitation['invitation']['slug']}/plays", {}, "completion-purge-play-01").json()
    complete(friend, replay, expected=reveals)
    other, other_owner, _ = gameplay()
    other_game = create(other, owned_seed(other_owner)).json()
    # Age only fixture timestamps within a rolled-back transaction. This proves
    # real expiry/purge predicates without waiting or installing a production clock override.
    with db_owner_engine.connect() as db:
        transaction = db.begin()
        try:
            db.execute(text("ALTER TABLE tasteduel.game_results DISABLE TRIGGER immutable_record"))
            db.execute(text("SELECT set_config('app.session_id',:id,true)"), {"id": replay["game_id"]})
            db.execute(text("CREATE POLICY fixture_age ON tasteduel.game_results FOR UPDATE TO tasteduel_migrator USING(true) WITH CHECK(true)"))
            db.execute(text("UPDATE tasteduel.game_results SET created_at=clock_timestamp()-interval '11 minutes' WHERE game_id=:id"), {"id": UUID(replay["game_id"])})
            assert not db.execute(text("SELECT tasteduel.session_live(:id)"), {"id": owner}).scalar_one()
            operations.purge(db, execute=True)
            assert db.execute(text("SELECT count(*) FROM tasteduel.games WHERE id IN(:source,:replay)"),
                {"source": UUID(source["game_id"]), "replay": UUID(replay["game_id"])}).scalar_one() == 0
            assert db.execute(text("SELECT count(*) FROM tasteduel.games WHERE id=:id"), {"id": UUID(other_game["game_id"])}).scalar_one() == 1
        finally:
            transaction.rollback()


def test_all_attempts_are_paginated_and_strangers_cannot_follow_cursor(gameplay, owned_seed):
    creator, _, _, source, reveals, invitation = shared(gameplay, owned_seed)
    slug = invitation["invitation"]["slug"]
    for number in range(1, 22):
        if (number - 1) % 7 == 0:
            friend, _, _ = gameplay()
            friend.post("/v1/sessions/name", json={"display_name": f"Friend {(number - 1) // 7 + 1}"})
        replay = post(friend, f"/v1/challenges/{slug}/plays", {"new_attempt": True}, f"pagination-attempt-{number:04d}")
        assert replay.status_code == 201, replay.json()
        # Each independent game has independent accepted-answer retry keys.
        complete(friend, replay.json(), expected=reveals)
    path = f"/v1/games/{source['game_id']}/duels"
    first = creator.get(path).json()
    assert len(first["outcomes"]) == 20 and first["next_cursor"]
    second = creator.get(path, params={"cursor": first["next_cursor"]}).json()
    assert len(second["outcomes"]) == 1 and second["next_cursor"] is None
    assert {(r["challenger_name"], r["attempt_number"]) for r in first["outcomes"] + second["outcomes"]} == {
        (f"Friend {friend}", number) for friend in range(1, 4) for number in range(1, 8)}
    stranger, _, _ = gameplay()
    assert stranger.get(path, params={"cursor": first["next_cursor"]}).status_code == 404
    assert creator.get(path, params={"cursor": "not-a-valid-cursor"}).status_code == 422
