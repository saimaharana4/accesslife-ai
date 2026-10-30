"""Exercise public HTTP serialization over a genuinely private PostgreSQL graph."""

import json
import time
from dataclasses import replace
from uuid import UUID, uuid4

import pytest

from tasteduel.persistence import models as m
from tasteduel.persistence.db import scoped_session

from ._seed import deliver, seed_private_graph


def _assert_private_graph_absent(payload, graph):
    rendered = json.dumps(payload, sort_keys=True)
    hidden = (
        *graph.private_markers,
        *graph.future_names,
        *(str(value) for value in graph.future_entity_ids),
        *(str(value) for value in graph.future_pair_ids),
        str(graph.snapshot_id),
        str(graph.first_pair_id),
    )
    for marker in hidden:
        assert marker not in rendered
    forbidden_keys = {
        "rank",
        "affinity",
        "query_context_hash",
        "snapshot_id",
        "pair_id",
        "private_pool",
        "raw_provider_payload",
        "chain_of_thought",
        "curation_receipt",
        "token_hash",
        "session_id",
        "idempotency_key",
        "provider_version",
        "harness_version",
        "model_version",
    }

    def inspect(value):
        if isinstance(value, dict):
            assert not forbidden_keys.intersection(value)
            for item in value.values():
                inspect(item)
        elif isinstance(value, list):
            for item in value:
                inspect(item)

    inspect(payload)


def _private_response(response, graph):
    assert response.status_code == 200
    assert "no-store" in response.headers.get("cache-control", "")
    payload = response.json()
    _assert_private_graph_absent(payload, graph)
    return payload


def test_unanswered_http_round_never_serializes_hidden_pool_or_answers(create_guest, db_owner_engine):
    client, owner_id = create_guest()
    graph = seed_private_graph(db_owner_engine, owner_id)
    playable = _private_response(client.get(f"/v1/games/{graph.game_id}/round"), graph)
    assert playable["state"] == "unanswered"
    assert playable["ordinal"] == 1
    assert [choice["id"] for choice in playable["choices"]] == [
        str(graph.first_left_choice_id),
        str(graph.first_right_choice_id),
    ]
    assert [choice["entity"]["name"] for choice in playable["choices"]] == [
        "Synthetic Current Left",
        "Synthetic Current Right",
    ]
    assert not {
        "winning_choice_id",
        "selected_choice_id",
        "correct",
        "evidence",
        "curation_summary",
        "answer",
        "answers",
        "future_rounds",
        "cumulative_score",
    }.intersection(playable)
    game = _private_response(client.get(f"/v1/games/{graph.game_id}"), graph)
    assert game["score"] == 0
    assert game["answered_count"] == 0
    assert game["current_round"]["state"] == "unanswered"
    assert "curation_summary" not in game
    assert "curation_summary" not in game["current_round"]


def test_accepted_current_reveal_restores_only_authorized_answer(create_guest, db_owner_engine):
    client, owner_id = create_guest()
    graph = seed_private_graph(db_owner_engine, owner_id, answered=True)
    game = _private_response(client.get(f"/v1/games/{graph.game_id}"), graph)
    reveal = game["current_round"]
    assert reveal["state"] == "revealed"
    assert reveal["round_id"] == str(graph.first_round_id)
    assert reveal["selected_choice_id"] == str(graph.first_left_choice_id)
    assert reveal["winning_choice_id"] == str(graph.first_right_choice_id)
    assert reveal["correct"] is False
    assert reveal["cumulative_score"] == game["score"] == 0
    assert game["answered_count"] == 1
    assert {reveal["selected_choice_id"], reveal["winning_choice_id"]} == {
        choice["id"] for choice in reveal["choices"]
    }
    if reveal.get("evidence"):
        assert reveal["evidence"]["source"] == "fixture"
        explanation = reveal["evidence"].get("supported_explanation")
        if explanation:
            assert explanation["kind"] in {"synthetic", "factual_template"}
    if reveal.get("curation_summary"):
        assert reveal["curation_summary"]["curator_mode"] == "fixture"
        assert reveal["curation_summary"]["candidate_count_received"] == 10
    # Refresh uses the accepted reveal through GamePublic. Asking for another
    # playable round cannot implicitly advance or return a future answer.
    response = client.get(f"/v1/games/{graph.game_id}/round")
    assert response.status_code == 409
    _assert_private_graph_absent(response.json(), graph)
    assert _private_response(client.get(f"/v1/games/{graph.game_id}"), graph) == game


def test_second_unanswered_round_drops_the_previous_accepted_reveal(create_guest, db_owner_engine):
    client, owner_id = create_guest()
    graph = seed_private_graph(db_owner_engine, owner_id, answered=True)
    before = _private_response(client.get(f"/v1/games/{graph.game_id}"), graph)
    assert before["current_round"]["state"] == "revealed"
    with scoped_session(db_owner_engine, owner_id) as db:
        pair = db.get(m.PrivatePair, graph.future_pair_ids[0])
        delivered, left, right = deliver(db, owner_id, graph.game_id, pair, 2)
        current_round_id, current_choice_ids = delivered.id, (left.id, right.id)
    # These two formerly private candidates have now legitimately been delivered;
    # the rest of the unused pool, and all private scoring facts, stay hidden.
    current_graph = replace(
        graph,
        future_names=graph.future_names[2:],
        future_entity_ids=graph.future_entity_ids[2:],
    )
    game = _private_response(client.get(f"/v1/games/{graph.game_id}"), current_graph)
    current = game["current_round"]
    assert game["current_ordinal"] == current["ordinal"] == 2
    assert game["answered_count"] == 1
    assert game["score"] == 0
    assert current["state"] == "unanswered"
    assert current["round_id"] == str(current_round_id)
    assert [choice["id"] for choice in current["choices"]] == [str(value) for value in current_choice_ids]
    assert not {
        "evidence",
        "curation_summary",
        "winning_choice_id",
        "selected_choice_id",
        "correct",
    }.intersection(current)
    rendered = json.dumps(game)
    for previous in (graph.first_round_id, graph.first_left_choice_id, graph.first_right_choice_id):
        assert str(previous) not in rendered
    assert "Synthetic Current Left" not in rendered
    assert "Synthetic Current Right" not in rendered
    # Even an attacker-supplied prior round query cannot restore its old reveal.
    response = client.get(f"/v1/games/{graph.game_id}/round", params={"round_id": str(graph.first_round_id)})
    assert _private_response(response, current_graph) == current


def test_expired_session_rejects_unchanged_cookie_and_hides_private_rows(
    api_client,
    db_owner_engine,
    db_engine,
    monkeypatch,
):
    monkeypatch.setattr(api_client.app.state.settings, "session_ttl_seconds", 2)
    response = api_client.post("/v1/sessions", json={})
    assert response.status_code == 201
    token = api_client.cookies.get("tasteduel_session")
    owner_id = UUID(token.split(".", 1)[0])
    graph = seed_private_graph(db_owner_engine, owner_id, answered=True)
    assert api_client.get(f"/v1/games/{graph.game_id}").status_code == 200
    time.sleep(2.1)
    # Force the original valid cookie back onto the request: this verifies
    # server expiry rather than merely HTTPX dropping an expired cookie.
    response = api_client.get(f"/v1/games/{graph.game_id}", headers={"Cookie": f"tasteduel_session={token}"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_REQUIRED"
    _assert_private_graph_absent(response.json(), graph)
    assert token not in response.text
    with scoped_session(db_engine, owner_id) as db:
        assert db.get(m.Session, owner_id) is not None
        assert db.get(m.Game, graph.game_id) is None


@pytest.mark.parametrize("suffix", ["", "/round", "/results"])
def test_other_guest_cannot_read_known_private_ids_or_spoof_owner_context(
    create_guest,
    db_owner_engine,
    suffix,
):
    owner_client, owner_id = create_guest()
    graph = seed_private_graph(db_owner_engine, owner_id, answered=True)
    stranger, _ = create_guest()
    response = stranger.get(
        f"/v1/games/{graph.game_id}{suffix}",
        params={"session_id": str(owner_id)},
        headers={
            "X-Session-Id": str(owner_id),
            "X-User-Id": str(owner_id),
            "X-Tasteduel-Session": str(owner_id),
        },
    )
    missing = stranger.get(f"/v1/games/{uuid4()}{suffix}")
    assert response.status_code == missing.status_code == 404
    assert response.json()["error"]["code"] == missing.json()["error"]["code"]
    assert response.json()["error"]["message"] == missing.json()["error"]["message"]
    _assert_private_graph_absent(response.json(), graph)
    assert "no-store" in response.headers.get("cache-control", "")
    assert owner_client.get(f"/v1/games/{graph.game_id}").status_code == 200


def test_session_clear_revokes_saved_cookie_access_without_revoking_another_guest(
    create_guest,
    db_owner_engine,
):
    client, owner_id = create_guest()
    graph = seed_private_graph(db_owner_engine, owner_id, answered=True)
    stranger, stranger_id = create_guest()
    other_graph = seed_private_graph(db_owner_engine, stranger_id)
    saved_cookies = dict(client.cookies)
    assert client.delete("/v1/sessions/current").status_code == 204
    client.cookies.update(saved_cookies)
    response = client.get(f"/v1/games/{graph.game_id}")
    assert response.status_code == 401
    _assert_private_graph_absent(response.json(), graph)
    assert stranger.get(f"/v1/games/{other_graph.game_id}").status_code == 200


@pytest.mark.parametrize(
    "malicious",
    [
        {"raw_provider_payload": {"credential": "PRIVATE_INPUT_MARKER"}},
        {"PRIVATE_INPUT_MARKER": "unknown field name must not be echoed"},
    ],
)
def test_rejected_request_never_echoes_input_in_validation_errors(create_guest, malicious):
    client, _ = create_guest()
    response = client.post(
        "/v1/games",
        json={
            "seed_entity_id": str(uuid4()),
            "seed_type": "artist",
            "mode": "solo",
            **malicious,
        },
        headers={"Idempotency-Key": "synthetic-rejected-request"},
    )
    assert response.status_code == 422
    assert "PRIVATE_INPUT_MARKER" not in response.text
    assert "input" not in response.json()["error"]
    assert "ctx" not in response.json()["error"]
    assert "no-store" in response.headers.get("cache-control", "")


def test_private_receipt_is_not_an_exported_http_contract(api_client):
    response = api_client.get("/openapi.json")
    assert response.status_code == 200
    components = response.json()["components"]["schemas"]
    assert "CurationReceipt" not in components
    assert "MutationReceipt" not in components
    assert "CurationSummaryPublic" in components


def test_completed_http_results_contain_exactly_five_accepted_rounds(create_guest, db_owner_engine):
    from sqlalchemy import select
    from tasteduel.persistence import models as m
    from tasteduel.persistence.db import scoped_session
    from ._seed import deliver

    client, owner = create_guest()
    graph = seed_private_graph(db_owner_engine, owner, answered=True)
    with scoped_session(db_owner_engine, owner) as db:
        for ordinal, pair_id in enumerate(graph.future_pair_ids, start=2):
            round_, _, right = deliver(db, owner, graph.game_id, db.get(m.PrivatePair, pair_id), ordinal)
            db.add(
                m.Answer(
                    session_id=owner,
                    game_id=graph.game_id,
                    round_id=round_.id,
                    choice_id=right.id,
                    idempotency_key=f"synthetic-result-{ordinal}",
                    correct=False,
                )
            )
            db.flush()
        answers = list(db.scalars(select(m.Answer).where(m.Answer.game_id == graph.game_id)))
        actual_score = sum(answer.correct for answer in answers)
        game = db.get(m.Game, graph.game_id)
        db.add(
            m.GameResult(
                session_id=owner, game_id=game.id, score=actual_score, scoring_version=game.scoring_version
            )
        )
    response = client.get(f"/v1/games/{graph.game_id}/results")
    assert response.status_code == 200
    result = response.json()
    assert result["score"] == actual_score == 4
    assert result["total"] == 5
    assert [round_["ordinal"] for round_ in result["answered_rounds"]] == [1, 2, 3, 4, 5]
    assert [round_["cumulative_score"] for round_ in result["answered_rounds"]] == [0, 1, 2, 3, 4]
    assert all(round_["state"] == "revealed" for round_ in result["answered_rounds"])
    assert "no-store" in response.headers["cache-control"]
    rendered = json.dumps(result)
    for marker in graph.private_markers:
        assert marker not in rendered
    assert "affinity" not in rendered and "curation_receipt" not in rendered


def test_untrusted_cookie_uuid_cannot_select_private_data_before_token_verification(
    create_guest,
    db_owner_engine,
    monkeypatch,
):
    from tasteduel.adapters.read_repository import SqlReadRepository

    client, owner_id = create_guest()
    graph = seed_private_graph(db_owner_engine, owner_id, answered=True)
    token = client.cookies.get("tasteduel_session")
    called = []
    original = SqlReadRepository.game

    def observe_game(repository, game_id):
        called.append(game_id)
        return original(repository, game_id)

    monkeypatch.setattr(SqlReadRepository, "game", observe_game)
    # Keep the correct UUID and change only one secret character. The UUID is
    # an untrusted row selector and must not become authorization by itself.
    forged = token[:-1] + ("A" if token[-1] != "A" else "B")
    client.cookies.clear()
    client.cookies.set("tasteduel_session", forged, domain="testserver.local", path="/")
    response = client.get(f"/v1/games/{graph.game_id}")
    assert response.status_code == 401
    _assert_private_graph_absent(response.json(), graph)
    assert called == []
    client.cookies.clear()
    client.cookies.set("tasteduel_session", token, domain="testserver.local", path="/")
    assert client.get(f"/v1/games/{graph.game_id}").status_code == 200
    assert called == [graph.game_id]


@pytest.mark.parametrize("content_length", [None, "0"])
def test_actual_body_limit_cannot_be_bypassed_by_missing_or_false_length(create_guest, content_length):
    client, _ = create_guest()
    body = json.dumps({"oversized": "x" * 17_000}).encode()
    request = client.build_request(
        "POST",
        "/v1/games",
        content=body,
        headers={
            "Content-Type": "application/json",
            "Idempotency-Key": "synthetic-oversized-request",
        },
    )
    if content_length is None:
        del request.headers["content-length"]
    else:
        request.headers["content-length"] = content_length
    response = client.send(request)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "REQUEST_TOO_LARGE"
    assert "oversized" not in response.text
    assert "no-store" in response.headers.get("cache-control", "")
