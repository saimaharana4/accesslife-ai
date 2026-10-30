"""Opt-in two-process test for private game/challenge persistence in Compose DB."""

import json
import os
from pathlib import Path
from uuid import UUID

import pytest

from .test_authoritative_flow import answer_body, create, next_body, post
from .conftest import SyntheticCurator


@pytest.mark.skipif(
    not os.environ.get("TASTEDUEL_PERSISTENCE_STATE_FILE"),
    reason="only the explicit runtime Compose persistence check writes local state",
)
def test_write_synthetic_completed_game_and_challenge_for_restart_check(gameplay, owned_seed):
    path = Path(os.environ["TASTEDUEL_PERSISTENCE_STATE_FILE"])
    path.parent.mkdir(parents=True, exist_ok=True)
    client, _, curator = gameplay(generator=SyntheticCurator())
    owner = UUID(client.cookies.get("tasteduel_session").split(".", 1)[0])
    created = create(client, owned_seed(owner))
    assert created.status_code == 201, created.json()
    game = created.json()
    first_round = game["current_round"]
    for index in range(5):
        current = game["current_round"]
        reveal_response = post(
            client,
            f"/v1/games/{game['game_id']}/answer",
            answer_body(current),
            f"compose-persistence-answer-{index + 1:02d}",
        )
        assert reveal_response.status_code == 200, reveal_response.json()
        advanced = post(
            client,
            f"/v1/games/{game['game_id']}/advance",
            next_body(reveal_response.json()),
            f"compose-persistence-advance-{index + 1:02d}",
        )
        assert advanced.status_code == 200, advanced.json()
        game = advanced.json()
    assert curator.calls == 1
    result = client.get(f"/v1/games/{game['game_id']}/results")
    assert result.status_code == 200, result.json()
    shared = post(
        client,
        "/v1/challenges",
        {"game_id": game["game_id"]},
        "compose-persistence-challenge-create-01",
    )
    assert shared.status_code == 201, shared.json()
    invitation = shared.json()["invitation"]
    assert invitation["source"] == "fixture"
    # Keep only the capability needed by the second, real-API process. This
    # ignored local file contains one synthetic session token and public slug.
    state = {
        "base_game_id": game["game_id"],
        "creator_cookie": client.cookies.get("tasteduel_session"),
        "creator_score": result.json()["score"],
        "slug": invitation["slug"],
        "seed_name": invitation["seed"]["name"],
        "first_choices": [choice["entity"]["name"] for choice in first_round["choices"]],
        "provider_calls": 0,
    }
    path.write_text(json.dumps(state), encoding="utf-8")
