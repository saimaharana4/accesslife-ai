"""Exact stored challenge replay, capability isolation and idempotency."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, update
import pytest

from tasteduel.persistence import models as m
from tasteduel.persistence.db import scoped_session

from .test_authoritative_flow import answer_body, create, next_body, post


def complete(client, game, *, choose_winner=None, expected=None):
    reveals = []
    for ordinal in range(1, 6):
        current = game["current_round"]
        if expected:
            assert [c["entity"]["name"] for c in current["choices"]] == [
                c["entity"]["name"] for c in expected[ordinal - 1]["choices"]
            ]
        body = answer_body(current)
        if choose_winner is not None:
            winner = expected[ordinal - 1]["winning_choice_id"]
            winner_name = next(
                c["entity"]["name"] for c in expected[ordinal - 1]["choices"] if c["id"] == winner
            )
            body["choice_id"] = next(
                c["id"] for c in current["choices"] if (c["entity"]["name"] == winner_name) == choose_winner
            )
        result = post(client, f"/v1/games/{game['game_id']}/answer", body, f"challenge-answer-{game['game_id']}-{ordinal:04d}")
        assert result.status_code == 200
        reveal = result.json()
        reveals.append(reveal)
        result = post(
            client,
            f"/v1/games/{game['game_id']}/advance",
            next_body(reveal),
            f"challenge-advance-{game['game_id']}-{ordinal:04d}",
        )
        assert result.status_code == 200
        game = result.json()
    return game, reveals


def shared(gameplay, owned_seed):
    client, owner, curator = gameplay()
    game = create(client, owned_seed(owner)).json()
    game, reveals = complete(client, game)
    response = post(client, "/v1/challenges", {"game_id": game["game_id"]}, "challenge-create-key-0001")
    assert response.status_code == 201, response.json()
    return client, owner, curator, game, reveals, response.json()


def test_two_guests_exact_frozen_rounds_independent_scores_no_providers(gameplay, owned_seed, db_engine):
    creator, owner, curator, source, reveals, shared_ = shared(gameplay, owned_seed)
    slug = shared_["invitation"]["slug"]
    assert len(slug) == 43
    public = creator.get(f"/v1/challenges/{slug}").json()
    assert set(public) == {"slug", "seed", "creator_name", "creator_score", "total", "source", "expires_at"}
    assert public["creator_score"] == source["score"]
    assert "session" not in str(public) and "winning" not in str(public)
    for correct in (True, False):
        client, guest, unused_curator = gameplay()
        response = post(client, f"/v1/challenges/{slug}/plays", {}, "challenge-play-key-0001")
        assert response.status_code == 201, response.json()
        game = response.json()
        assert game["mode"] == "fixed"
        assert post(client, f"/v1/challenges/{slug}/plays", {}, "challenge-play-key-0001").json() == game
        assert creator.get(f"/v1/games/{game['game_id']}").status_code == 404
        assert client.get(f"/v1/games/{source['game_id']}").status_code == 404
        game, replay = complete(client, game, choose_winner=correct, expected=reveals)
        assert game["score"] == (5 if correct else 0)
        assert unused_curator.calls == 0
        with scoped_session(db_engine, guest) as db:
            assert (
                db.scalar(select(m.Game.selection_version).where(m.Game.id == UUID(game["game_id"])))
                == "fixed-path-v1"
            )
    assert curator.calls == 1


@pytest.mark.parametrize("state", ["expired", "revoked"])
def test_public_invitation_does_not_require_an_unrelated_guest_cookie(
    gameplay, owned_seed, db_engine, expired_guest_cookie, state
):
    _, _, _, _, _, share = shared(gameplay, owned_seed)
    guest, owner, _ = gameplay()
    if state == "expired":
        guest.cookies.set("tasteduel_session", expired_guest_cookie, domain="testserver.local", path="/")
    else:
        with scoped_session(db_engine, owner) as db:
            row = db.get(m.Session, owner)
            row.revoked_at = datetime.now(UTC)
    assert guest.get("/v1/sessions/current").status_code == 401
    invitation = guest.get(f"/v1/challenges/{share['invitation']['slug']}")
    assert invitation.status_code == 200
    assert invitation.json() == share["invitation"]
    assert (
        guest.post(
            f"/v1/challenges/{share['invitation']['slug']}/plays",
            json={},
            headers={"Idempotency-Key": "stale-guest-play-denied-0001"},
        ).status_code
        == 401
    )


def test_create_idempotency_concurrent_retries_and_changed_body(gameplay, owned_seed):
    client, _, _, game, _, shared_ = shared(gameplay, owned_seed)

    def retry(_):
        return post(client, "/v1/challenges", {"game_id": game["game_id"]}, "challenge-create-key-0001")

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(retry, range(3)))
    assert all(r.status_code == 200 and r.json() == shared_ for r in results)
    changed = post(client, "/v1/challenges", {"game_id": str(UUID(int=123))}, "challenge-create-key-0001")
    assert changed.status_code == 409


def test_revocation_blocks_invitation_existing_replay_and_mutations(gameplay, owned_seed):
    creator, _, _, _, _, share = shared(gameplay, owned_seed)
    slug = share["invitation"]["slug"]
    guest, _, _ = gameplay()
    game = post(guest, f"/v1/challenges/{slug}/plays", {}, "challenge-play-key-0001").json()
    assert guest.delete(f"/v1/challenges/{slug}").status_code == 404
    assert creator.delete(f"/v1/challenges/{slug}").status_code == 204
    assert creator.delete(f"/v1/challenges/{slug}").status_code == 204
    assert guest.get(f"/v1/challenges/{slug}").status_code == 410
    assert guest.get(f"/v1/games/{game['game_id']}").status_code == 410
    assert (
        post(
            guest,
            f"/v1/games/{game['game_id']}/answer",
            answer_body(game["current_round"]),
            "revoked-answer-key-0001",
        ).status_code
        == 410
    )


def test_creator_session_clear_revokes_guest_replay(gameplay, owned_seed):
    creator, _, _, _, _, share = shared(gameplay, owned_seed)
    slug = share["invitation"]["slug"]
    guest, _, _ = gameplay()
    game = post(guest, f"/v1/challenges/{slug}/plays", {}, "challenge-play-key-0001").json()
    assert creator.delete("/v1/sessions/current").status_code == 204
    assert guest.get(f"/v1/challenges/{slug}").status_code == 410
    assert guest.get(f"/v1/games/{game['game_id']}").status_code == 410


def test_concurrent_play_retries_publish_one_game_and_no_future_answer_leaks(gameplay, owned_seed, db_engine):
    _, _, _, _, _, share = shared(gameplay, owned_seed)
    slug = share["invitation"]["slug"]
    guest, owner, unused = gameplay()

    def retry(_):
        return post(guest, f"/v1/challenges/{slug}/plays", {}, "concurrent-play-key-0001")

    with ThreadPoolExecutor(max_workers=3) as pool:
        responses = list(pool.map(retry, range(3)))
    assert sorted(r.status_code for r in responses) == [200, 200, 201]
    assert len({r.json()["game_id"] for r in responses}) == 1
    game = responses[0].json()
    for path in (f"/v1/games/{game['game_id']}", f"/v1/games/{game['game_id']}/round"):
        response = guest.get(path)
        assert response.status_code == 200
        assert not {"winning_choice_id", "affinity", "rank", "winner_entity_id"}.intersection(
            str(response.json()).split()
        )
    assert guest.get(f"/v1/games/{game['game_id']}/results").status_code == 409
    with scoped_session(db_engine, owner) as db:
        assert db.scalar(select(func.count()).select_from(m.ChallengePlay)) == 1
        assert db.scalar(select(func.count()).select_from(m.DeliveredRound)) == 1
        assert db.scalar(select(func.count()).select_from(m.PrivatePair)) == 5
    assert unused.calls == 0


def test_challenge_expiry_never_requeries_or_replaces_rounds(gameplay, owned_seed, db_engine):
    creator, owner, curator, _, _, share = shared(gameplay, owned_seed)
    slug = share["invitation"]["slug"]
    guest, _, unused = gameplay()
    game = post(guest, f"/v1/challenges/{slug}/plays", {}, "challenge-play-key-0001").json()
    import time

    expiry = datetime.now(UTC) + timedelta(milliseconds=70)
    with scoped_session(db_engine, owner) as db:
        db.execute(update(m.Challenge).where(m.Challenge.share_slug == slug).values(expires_at=expiry))
    time.sleep(0.09)
    assert guest.get(f"/v1/challenges/{slug}").status_code == 410
    # Its sole linked session now expires with the challenge lifecycle.
    assert guest.get(f"/v1/games/{game['game_id']}").status_code == 401
    assert post(guest, f"/v1/challenges/{slug}/plays", {}, "expired-new-play-key-0001").status_code == 401
    assert curator.calls == 1 and unused.calls == 0


def test_later_provider_ranking_is_irrelevant_to_frozen_challenge(gameplay, owned_seed):
    creator, _, curator, _, reveals, share = shared(gameplay, owned_seed)

    # A provider implementation that would now fail cannot affect stored replay.
    async def unavailable(*args, **kwargs):
        raise AssertionError("Replay must never consult current provider rankings")

    curator.curate = unavailable
    guest, _, guest_curator = gameplay()
    guest_curator.curate = unavailable
    game = post(
        guest, f"/v1/challenges/{share['invitation']['slug']}/plays", {}, "changed-provider-key-0001"
    ).json()
    result, _ = complete(guest, game, choose_winner=True, expected=reveals)
    assert result["score"] == 5


def test_incomplete_source_and_arbitrary_slug_fail_without_source_leak(gameplay, owned_seed):
    client, owner, _ = gameplay()
    game = create(client, owned_seed(owner)).json()
    assert (
        post(client, "/v1/challenges", {"game_id": game["game_id"]}, "incomplete-share-key-0001").status_code
        == 409
    )
    assert client.get("/v1/challenges/" + "A" * 43).status_code == 404
    assert (
        post(client, "/v1/challenges/" + "A" * 43 + "/plays", {}, "unknown-slug-play-key-0001").status_code
        == 404
    )


def test_fixed_replay_cannot_fork_around_creator_revocation(gameplay, owned_seed):
    _, _, _, _, reveals, share = shared(gameplay, owned_seed)
    guest, _, _ = gameplay()
    game = post(
        guest, f"/v1/challenges/{share['invitation']['slug']}/plays", {}, "no-fork-play-key-0001"
    ).json()
    completed, _ = complete(guest, game, choose_winner=True, expected=reveals)
    result = guest.get(f"/v1/games/{completed['game_id']}/results")
    assert result.status_code == 200 and result.json()["mode"] == "fixed"
    response = post(guest, "/v1/challenges", {"game_id": completed["game_id"]}, "no-fork-share-key-0001")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CHALLENGE_RESHARE_UNAVAILABLE"


def test_revocation_removes_replay_only_discovery_evidence(gameplay, owned_seed):
    creator, _, _, _, _, share = shared(gameplay, owned_seed)
    slug = share["invitation"]["slug"]
    guest, _, _ = gameplay()
    game = post(guest, f"/v1/challenges/{slug}/plays", {}, "discovery-play-key-0001").json()
    current = game["current_round"]
    accepted = post(
        guest, f"/v1/games/{game['game_id']}/answer", answer_body(current), "discovery-answer-key-0001"
    )
    assert accepted.status_code == 200
    entity_id = current["choices"][0]["entity"]["id"]
    saved = post(guest, "/v1/discoveries", {"entity_id": entity_id}, "replay-save-key-0001")
    assert saved.status_code == 201
    assert len(guest.get("/v1/discoveries").json()["discoveries"]) == 1
    assert creator.delete(f"/v1/challenges/{slug}").status_code == 204
    collection = guest.get("/v1/discoveries").json()
    assert collection["discoveries"] == [] and collection["expired_count"] == 1
    assert (
        post(guest, "/v1/discoveries", {"entity_id": entity_id}, "revoked-save-key-0001").status_code == 404
    )
