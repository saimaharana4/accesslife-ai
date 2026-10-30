"""Probe real HTTP reads/mutations against PostgreSQL-owned hidden game state.

The graph is synthetic and deliberately includes unmistakable private markers.
These checks observe public responses, rather than trusting DTO field names.
"""

import json
from uuid import uuid4

import pytest

from tasteduel.persistence import models as m

from quality.tasteduel.security._seed import seed_private_graph
from quality.tasteduel.security.test_api_secrecy import _assert_private_graph_absent


def _poisoned_graph(engine, owner, monkeypatch, *, answered=False):
    """Persist a valid receipt whose private strategy statistics are distinctive.

    Inject only at construction, before immutable rows are committed. The
    application still reads/serializes the actual PostgreSQL receipt normally.
    """
    receipt_type = m.CurationReceipt

    def receipt(**values):
        return receipt_type(
            **{
                **values,
                "rejection_counts": {"near_tie": 7},
                "bounded_correction_count": 1,
            }
        )

    with monkeypatch.context() as context:
        context.setattr(m, "CurationReceipt", receipt)
        return seed_private_graph(engine, owner, answered=answered)


def _assert_no_strategy_details(payload):
    """Even an earlier reveal must not disclose answer-dependent pool findings."""
    forbidden = {
        "rejection_counts",
        "candidate_count_rejected",
        "evaluation_feedback",
        "final_feedback",
        "action_trace",
        "bounded_correction_count",
        "policy_fingerprint",
        "final_pool_status",
        "five_round_path",
        "winning_side",
    }

    def inspect(value):
        if isinstance(value, dict):
            assert value.get("curation_summary") is None
            assert not forbidden.intersection(value)
            for nested in value.values():
                inspect(nested)
        elif isinstance(value, list):
            for nested in value:
                inspect(nested)

    inspect(payload)


@pytest.mark.parametrize("answered", [False, True])
def test_every_owned_read_suppresses_private_pool_and_unfinished_curation(
    create_guest, db_owner_engine, monkeypatch, answered
):
    client, owner = create_guest()
    graph = _poisoned_graph(db_owner_engine, owner, monkeypatch, answered=answered)
    expected = {
        "/v1/sessions/current": 200,
        f"/v1/games/{graph.game_id}": 200,
        f"/v1/games/{graph.game_id}/round": 409 if answered else 200,
        f"/v1/games/{graph.game_id}/results": 409,
        "/v1/discoveries": 200,
    }
    for path, status in expected.items():
        response = client.get(
            path,
            params={
                "include": "receipt,pool,answers,raw_provider_payload",
                "round_id": str(graph.future_pair_ids[-1]),
                "snapshot_id": str(graph.snapshot_id),
            },
        )
        assert response.status_code == status
        assert "no-store" in response.headers.get("cache-control", "")
        _assert_private_graph_absent(response.json(), graph)
        _assert_no_strategy_details(response.json())


@pytest.mark.parametrize("suffix", ["receipt", "curation", "pool", "answers", "rounds", "status"])
def test_undocumented_private_subresources_do_not_become_debug_backdoors(
    create_guest, db_owner_engine, suffix
):
    client, owner = create_guest()
    graph = seed_private_graph(db_owner_engine, owner)
    response = client.get(f"/v1/games/{graph.game_id}/{suffix}")
    assert response.status_code == 404
    _assert_private_graph_absent(response.json(), graph)
    _assert_no_strategy_details(response.json())


@pytest.mark.parametrize("operation", ["answer", "advance"])
def test_other_session_cannot_mutate_known_game_or_probe_answer_truth(
    create_guest, db_owner_engine, operation
):
    owner_client, owner = create_guest()
    graph = seed_private_graph(db_owner_engine, owner)
    stranger, _ = create_guest()
    revision = owner_client.get(f"/v1/games/{graph.game_id}").json()["revision"]
    body = (
        {
            "round_id": str(graph.first_round_id),
            "choice_id": str(graph.first_right_choice_id),
            "expected_revision": revision,
        }
        if operation == "answer"
        else {"answered_round_id": str(graph.first_round_id), "expected_revision": revision}
    )
    response = stranger.post(
        f"/v1/games/{graph.game_id}/{operation}",
        json=body,
        headers={"Idempotency-Key": "independent-security-cross-owner"},
    )
    missing = stranger.post(
        f"/v1/games/{uuid4()}/{operation}",
        json=body,
        headers={"Idempotency-Key": "independent-security-missing-game"},
    )
    assert response.status_code == missing.status_code == 404
    assert response.json()["error"]["code"] == missing.json()["error"]["code"]
    _assert_private_graph_absent(response.json(), graph)
    still_playable = owner_client.get(f"/v1/games/{graph.game_id}").json()
    assert still_playable["answered_count"] == 0
    assert still_playable["score"] == 0


@pytest.mark.parametrize(
    "invalid_id_kind", ["unknown_round", "private_pair", "future_entity", "other_choice"]
)
def test_valid_uuid_attacks_cannot_answer_a_future_or_different_pair(
    create_guest, db_owner_engine, invalid_id_kind
):
    client, owner = create_guest()
    graph = seed_private_graph(db_owner_engine, owner)
    _, second_owner = create_guest()
    second_graph = seed_private_graph(db_owner_engine, second_owner)
    revision = client.get(f"/v1/games/{graph.game_id}").json()["revision"]
    round_id, choice_id = graph.first_round_id, graph.first_left_choice_id
    if invalid_id_kind == "unknown_round":
        round_id = uuid4()
    elif invalid_id_kind == "private_pair":
        round_id = graph.future_pair_ids[0]
    elif invalid_id_kind == "future_entity":
        choice_id = graph.future_entity_ids[0]
    else:
        choice_id = second_graph.first_right_choice_id
    response = client.post(
        f"/v1/games/{graph.game_id}/answer",
        json={
            "round_id": str(round_id),
            "choice_id": str(choice_id),
            "expected_revision": revision,
        },
        headers={"Idempotency-Key": f"independent-security-{invalid_id_kind}"},
    )
    assert response.status_code in {404, 409}
    _assert_private_graph_absent(response.json(), graph)
    _assert_no_strategy_details(response.json())
    state = client.get(f"/v1/games/{graph.game_id}").json()
    assert state["current_round"]["state"] == "unanswered"
    assert state["answered_count"] == state["score"] == 0


@pytest.mark.parametrize("operation", ["answer", "advance"])
def test_cleared_session_saved_cookie_cannot_mutate_existing_game(create_guest, db_owner_engine, operation):
    client, owner = create_guest()
    graph = seed_private_graph(db_owner_engine, owner)
    before = client.get(f"/v1/games/{graph.game_id}").json()
    token = client.cookies.get("tasteduel_session")
    assert client.delete("/v1/sessions/current").status_code == 204
    body = (
        {
            "round_id": str(graph.first_round_id),
            "choice_id": str(graph.first_left_choice_id),
            "expected_revision": before["revision"],
        }
        if operation == "answer"
        else {"answered_round_id": str(graph.first_round_id), "expected_revision": before["revision"]}
    )
    response = client.post(
        f"/v1/games/{graph.game_id}/{operation}",
        json=body,
        headers={
            "Cookie": f"tasteduel_session={token}",
            "Idempotency-Key": "independent-security-revoked-session",
        },
    )
    assert response.status_code == 401
    assert token not in response.text
    _assert_private_graph_absent(response.json(), graph)


@pytest.mark.parametrize("operation", ["answer", "advance"])
def test_invalid_mutation_fields_and_keys_never_echo_attacker_input(create_guest, db_owner_engine, operation):
    client, owner = create_guest()
    graph = seed_private_graph(db_owner_engine, owner)
    marker = "PRIVATE_ATTACKER_CONTROLLED_PAYLOAD"
    response = client.post(
        f"/v1/games/{graph.game_id}/{operation}",
        json={"round_id": marker, "choice_id": marker, marker: marker},
        headers={"Idempotency-Key": marker + "/../bad-key"},
    )
    assert response.status_code == 422
    assert marker not in response.text
    assert "no-store" in response.headers.get("cache-control", "")
    _assert_private_graph_absent(response.json(), graph)


def test_mutation_origin_rejected_before_game_state_is_read(create_guest, db_owner_engine):
    client, owner = create_guest()
    graph = seed_private_graph(db_owner_engine, owner)
    response = client.post(
        f"/v1/games/{graph.game_id}/answer",
        json={
            "round_id": str(graph.first_round_id),
            "choice_id": str(graph.first_right_choice_id),
            "expected_revision": 0,
        },
        headers={"Origin": "https://attacker.invalid", "Idempotency-Key": "independent-security-bad-origin"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ORIGIN_NOT_ALLOWED"
    _assert_private_graph_absent(response.json(), graph)
    current = client.get(f"/v1/games/{graph.game_id}").json()
    assert current["answered_count"] == 0
    assert "winning_choice_id" not in json.dumps(current)
