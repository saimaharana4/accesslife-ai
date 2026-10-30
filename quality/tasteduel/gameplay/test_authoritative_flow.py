"""HTTP retries and concurrency exercise the actual PostgreSQL authority."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
import json
import time
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update

from tasteduel.persistence import models as m
from tasteduel.persistence.db import scoped_session

from .conftest import SyntheticCurator


def post(client, path, body, key):
    return client.post(path, json=body, headers={"Idempotency-Key": key})


def create(client, body, key="synthetic-create-key-0001"):
    return post(client, "/v1/games", body, key)


def game(client, identifier):
    response = client.get(f"/v1/games/{identifier}")
    assert response.status_code == 200
    return response.json()


def counts(engine, owner, game_id):
    with scoped_session(engine, owner) as db:
        return {
            table.__tablename__: db.scalar(
                select(func.count()).select_from(table).where(table.game_id == UUID(game_id))
            )
            for table in (
                m.CurationReceipt,
                m.GenerationReservation,
                m.DeliveredRound,
                m.Answer,
                m.GameResult,
            )
        }


def answer_body(current):
    return {
        "round_id": current["round_id"],
        "choice_id": current["choices"][0]["id"],
        "expected_revision": current["revision"],
    }


def next_body(reveal):
    return {"answered_round_id": reveal["round_id"], "expected_revision": reveal["revision"]}


def test_five_round_authoritative_flow_score_reload_and_no_generation_on_answer_or_next(
    gameplay, owned_seed, db_engine
):
    client, owner, curator = gameplay()
    created = create(client, owned_seed(owner))
    assert created.status_code == 201
    identifier = created.json()["game_id"]
    expected_score = 0
    seen = set()
    for ordinal in range(1, 6):
        current = game(client, identifier)["current_round"]
        assert current["state"] == "unanswered" and current["ordinal"] == ordinal
        assert not {"winning_choice_id", "curation_summary", "affinity", "rank"}.intersection(current)
        for choice in current["choices"]:
            assert choice["entity"]["id"] not in seen
            seen.add(choice["entity"]["id"])
        with scoped_session(db_engine, owner) as db:
            stored_winner = db.scalar(
                select(m.PrivatePair.winner_entity_id)
                .join(m.DeliveredRound, m.DeliveredRound.pair_id == m.PrivatePair.id)
                .where(m.DeliveredRound.id == UUID(current["round_id"]))
            )
        expected_correct = stored_winner == UUID(current["choices"][0]["entity"]["id"])
        submitted = post(
            client, f"/v1/games/{identifier}/answer", answer_body(current), f"synthetic-answer-{ordinal:04d}"
        )
        assert submitted.status_code == 200
        reveal = submitted.json()
        assert reveal["correct"] is expected_correct
        expected_score += int(expected_correct)
        assert reveal["cumulative_score"] == expected_score
        assert reveal["winning_choice_id"] in {choice["id"] for choice in current["choices"]}
        assert game(client, identifier)["current_round"] == reveal
        if ordinal < 5:
            assert reveal.get("curation_summary") is None
        advanced = post(
            client, f"/v1/games/{identifier}/advance", next_body(reveal), f"synthetic-advance-{ordinal:04d}"
        )
        assert advanced.status_code == 200
        assert curator.calls == 1
    result = client.get(f"/v1/games/{identifier}/results")
    assert result.status_code == 200
    assert result.json()["score"] == expected_score
    assert result.json()["total"] == 5
    assert len(result.json()["answered_rounds"]) == 5
    assert len(seen) == 10
    assert counts(db_engine, owner, identifier) == {
        "curation_receipts": 1,
        "generation_reservations": 1,
        "delivered_rounds": 5,
        "answers": 5,
        "game_results": 1,
    }


def test_lost_create_response_and_api_restart_resolve_same_game_and_receipt(gameplay, owned_seed, db_engine):
    client, owner, curator = gameplay()
    body = owned_seed(owner)
    first = create(client, body)
    assert first.status_code == 201
    identifier = first.json()["game_id"]
    cookie = client.cookies.get("tasteduel_session")
    restarted, _, replacement = gameplay(cookie=cookie)
    retried = create(restarted, body)
    assert retried.status_code == 200 and retried.json() == first.json()
    assert curator.calls == 1 and replacement.calls == 0
    assert counts(db_engine, owner, identifier)["curation_receipts"] == 1
    with scoped_session(db_engine, owner) as db:
        receipt = db.scalar(select(m.CurationReceipt).where(m.CurationReceipt.game_id == UUID(identifier)))
        assert receipt.full_receipt["game_id"] == identifier
        assert receipt.full_receipt["provider_version"] == curator.outcomes[0].receipt.provider_version
        assert receipt.full_receipt["action_trace"][0]["tool"] == "finish_pool"


def test_changed_create_body_with_same_key_is_conflict(gameplay, owned_seed):
    client, owner, curator = gameplay()
    assert create(client, owned_seed(owner)).status_code == 201
    changed = create(client, owned_seed(owner))
    assert changed.status_code == 409
    assert curator.calls == 1


def test_failed_awaited_generation_leaves_no_partial_pool_then_retry_reuses_reservation(
    gameplay, owned_seed, db_engine
):
    class FailOnceCurator(SyntheticCurator):
        failed = False

        async def curate(self, *args, **kwargs):
            if not self.failed:
                self.failed = True
                self.calls += 1
                raise RuntimeError("SYNTHETIC_PRIVATE_PROVIDER_DIAGNOSTIC")
            return await super().curate(*args, **kwargs)

    client, owner, curator = gameplay(generator=FailOnceCurator())
    body = owned_seed(owner)
    failed = create(client, body)
    assert failed.status_code == 503
    assert "SYNTHETIC_PRIVATE_PROVIDER_DIAGNOSTIC" not in failed.text
    with scoped_session(db_engine, owner) as db:
        reservation = db.scalar(
            select(m.GenerationReservation).where(m.GenerationReservation.session_id == owner)
        )
        identifier = str(reservation.game_id)
        assert reservation.status == "failed" and reservation.lease_owner is None
    assert counts(db_engine, owner, identifier)["curation_receipts"] == 0
    assert counts(db_engine, owner, identifier)["delivered_rounds"] == 0
    retry = create(client, body)
    assert retry.status_code in (200, 201)
    assert retry.json()["game_id"] == identifier and curator.calls == 2
    assert counts(db_engine, owner, identifier)["curation_receipts"] == 1


def test_concurrent_create_observes_running_request_and_publishes_one_receipt(
    gameplay, owned_seed, db_engine
):
    curator = SyntheticCurator(block_first=True)
    client, owner, _ = gameplay(generator=curator)
    body = owned_seed(owner)
    second, _, _ = gameplay(generator=curator, cookie=client.cookies.get("tasteduel_session"))
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(create, client, body)
        assert curator.started.wait(5)
        try:
            observed = create(second, body)
            assert observed.status_code == 202
            pending = observed.json()
            assert pending["status"] == "generation_in_progress"
            assert set(pending) <= {"game_id", "status", "retry_after_seconds", "lease_expires_at"}
            status = second.get(f"/v1/games/{pending['game_id']}/generation")
            assert status.status_code == 200
            assert status.json()["status"] == "generation_in_progress"
        finally:
            curator.release.set()
        ready = first.result(5)
    assert ready.status_code == 201
    assert ready.json()["game_id"] == pending["game_id"]
    assert curator.calls == 1
    assert counts(db_engine, owner, pending["game_id"])["curation_receipts"] == 1


def test_expired_claim_reclaimed_after_restart_fences_old_publisher(gameplay, owned_seed, db_engine):
    curator = SyntheticCurator(block_first=True)
    client, owner, _ = gameplay(generator=curator)
    body = owned_seed(owner)
    with ThreadPoolExecutor(max_workers=2) as executor:
        old = executor.submit(create, client, body)
        assert curator.started.wait(5)
        try:
            with scoped_session(db_engine, owner) as db:
                reservation = db.scalar(
                    select(m.GenerationReservation).where(m.GenerationReservation.session_id == owner)
                )
                identifier = str(reservation.game_id)
                first_fence = reservation.fence
                reservation.deadline_at = datetime.now(UTC) + timedelta(milliseconds=50)
                reservation.lease_expires_at = datetime.now(UTC) + timedelta(milliseconds=100)
            time.sleep(0.12)
            restarted, _, fresh = gameplay(cookie=client.cookies.get("tasteduel_session"))
            status = restarted.get(f"/v1/games/{identifier}/generation")
            assert status.status_code == 200 and status.json()["status"] == "retryable"
            reclaimed = create(restarted, body)
            assert reclaimed.status_code in (200, 201)
            assert reclaimed.json()["game_id"] == identifier and fresh.calls == 1
        finally:
            curator.release.set()
        stale = old.result(5)
    assert stale.status_code in (200, 409)
    with scoped_session(db_engine, owner) as db:
        reservation = db.scalar(
            select(m.GenerationReservation).where(m.GenerationReservation.game_id == UUID(identifier))
        )
        assert reservation.fence > first_fence and reservation.attempt_count == 2
        assert reservation.status == "succeeded"
        receipt = db.scalar(select(m.CurationReceipt).where(m.CurationReceipt.game_id == UUID(identifier)))
        assert receipt.full_receipt["provider_version"] == fresh.outcomes[0].receipt.provider_version
        assert receipt.full_receipt["provider_version"] != curator.outcomes[0].receipt.provider_version
    assert counts(db_engine, owner, identifier)["curation_receipts"] == 1


def test_session_clear_during_generation_prevents_publication(gameplay, owned_seed, db_owner_engine, db_engine):
    curator = SyntheticCurator(block_first=True)
    client, owner, _ = gameplay(generator=curator)
    body = owned_seed(owner)
    observer, _, _ = gameplay(cookie=client.cookies.get("tasteduel_session"))
    with ThreadPoolExecutor(max_workers=2) as executor:
        pending = executor.submit(create, client, body)
        assert curator.started.wait(5)
        try:
            assert observer.delete("/v1/sessions/current").status_code == 204
        finally:
            curator.release.set()
        response = pending.result(5)
    assert response.status_code in (401, 409, 410)
    with scoped_session(db_owner_engine, owner) as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(m.CurationReceipt)
                .where(m.CurationReceipt.session_id == owner)
            )
            == 0
        )
        reservation = db.scalar(
            select(m.GenerationReservation).where(m.GenerationReservation.session_id == owner)
        )
        # Maintenance identity can inspect durable cancellation; it must not
        # publish a pool/receipt after the owner's access was revoked.
        assert reservation is not None and reservation.status == "cancelled"
        assert db.get(m.Session, owner).revoked_at is not None
    with scoped_session(db_engine, owner) as db:
        # Browser runtime retains the revoked-session FORCE RLS boundary.
        assert db.scalar(select(m.GenerationReservation).where(m.GenerationReservation.session_id == owner)) is None
        assert db.scalar(select(m.CurationReceipt).where(m.CurationReceipt.session_id == owner)) is None


def test_concurrent_identical_answers_accept_once_and_return_saved_reveal(gameplay, owned_seed, db_engine):
    client, owner, _ = gameplay()
    created = create(client, owned_seed(owner)).json()
    identifier, current = created["game_id"], created["current_round"]
    other, _, _ = gameplay(cookie=client.cookies.get("tasteduel_session"))
    body = answer_body(current)
    with ThreadPoolExecutor(max_workers=2) as executor:
        replies = list(
            executor.map(
                lambda c: post(c, f"/v1/games/{identifier}/answer", body, "same-answer-key-0001"),
                (client, other),
            )
        )
    assert [reply.status_code for reply in replies] == [200, 200]
    assert replies[0].json() == replies[1].json()
    assert counts(db_engine, owner, identifier)["answers"] == 1
    changed = {**body, "choice_id": current["choices"][1]["id"]}
    assert post(client, f"/v1/games/{identifier}/answer", changed, "same-answer-key-0001").status_code == 409
    assert post(client, f"/v1/games/{identifier}/answer", changed, "other-answer-key-001").status_code == 409


def test_concurrent_conflicting_answers_accept_exactly_one(gameplay, owned_seed, db_engine):
    client, owner, _ = gameplay()
    created = create(client, owned_seed(owner)).json()
    identifier, current = created["game_id"], created["current_round"]
    other, _, _ = gameplay(cookie=client.cookies.get("tasteduel_session"))
    bodies = [answer_body(current), {**answer_body(current), "choice_id": current["choices"][1]["id"]}]
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(post, c, f"/v1/games/{identifier}/answer", b, f"conflict-answer-{i:04d}")
            for i, (c, b) in enumerate(zip((client, other), bodies))
        ]
        replies = [future.result(5) for future in futures]
    assert sorted(reply.status_code for reply in replies) == [200, 409]
    assert counts(db_engine, owner, identifier)["answers"] == 1


def test_lost_answer_and_advance_responses_restore_the_same_saved_result_after_restart(
    gameplay, owned_seed, db_engine
):
    client, owner, curator = gameplay()
    created = create(client, owned_seed(owner)).json()
    identifier, current = created["game_id"], created["current_round"]
    answer_request = answer_body(current)
    first_answer = post(client, f"/v1/games/{identifier}/answer", answer_request, "restart-answer-key-01")
    assert first_answer.status_code == 200
    advance_request = next_body(first_answer.json())
    first_next = post(client, f"/v1/games/{identifier}/advance", advance_request, "restart-advance-key-1")
    assert first_next.status_code == 200
    restarted, _, untouched = gameplay(cookie=client.cookies.get("tasteduel_session"))
    answer_retry = post(restarted, f"/v1/games/{identifier}/answer", answer_request, "restart-answer-key-01")
    next_retry = post(restarted, f"/v1/games/{identifier}/advance", advance_request, "restart-advance-key-1")
    assert answer_retry.status_code == 200 and answer_retry.json() == first_answer.json()
    assert next_retry.status_code == 200 and next_retry.json() == first_next.json()
    assert curator.calls == 1 and untouched.calls == 0
    assert counts(db_engine, owner, identifier)["answers"] == 1
    assert counts(db_engine, owner, identifier)["delivered_rounds"] == 2


def test_concurrent_advance_delivers_once_and_reused_key_changed_body_conflicts(
    gameplay, owned_seed, db_engine
):
    client, owner, _ = gameplay()
    created = create(client, owned_seed(owner)).json()
    identifier = created["game_id"]
    reveal = post(
        client,
        f"/v1/games/{identifier}/answer",
        answer_body(created["current_round"]),
        "advance-answer-key-01",
    ).json()
    other, _, _ = gameplay(cookie=client.cookies.get("tasteduel_session"))
    with ThreadPoolExecutor(max_workers=2) as executor:
        replies = list(
            executor.map(
                lambda c: post(
                    c, f"/v1/games/{identifier}/advance", next_body(reveal), "same-advance-key-001"
                ),
                (client, other),
            )
        )
    assert [response.status_code for response in replies] == [200, 200]
    assert replies[0].json() == replies[1].json()
    assert replies[0].json()["current_round"]["ordinal"] == 2
    assert counts(db_engine, owner, identifier)["delivered_rounds"] == 2
    changed = {**next_body(reveal), "answered_round_id": str(uuid4())}
    assert post(client, f"/v1/games/{identifier}/advance", changed, "same-advance-key-001").status_code == 409


@pytest.mark.parametrize("malicious", ["not-a-uuid", "../answer", "00000000-0000-0000-0000-000000000000"])
def test_malicious_or_unknown_ids_do_not_reveal_private_data(gameplay, malicious):
    client, _, curator = gameplay()
    for suffix in ("", "/round", "/generation", "/results"):
        response = client.get(f"/v1/games/{malicious}{suffix}")
        assert response.status_code in (404, 422)
        assert "winning_choice_id" not in response.text and "affinity" not in response.text
    assert curator.calls == 0


def test_isolated_sessions_cannot_read_or_mutate_game_or_use_foreign_seed(gameplay, owned_seed):
    owner_client, owner, _ = gameplay()
    foreign, _, foreign_curator = gameplay()
    seed = owned_seed(owner)
    created = create(owner_client, seed).json()
    identifier = created["game_id"]
    assert create(foreign, seed).status_code == 404
    assert foreign_curator.calls == 0
    for suffix in ("", "/round", "/generation", "/results"):
        assert foreign.get(f"/v1/games/{identifier}{suffix}").status_code == 404
    assert (
        post(
            foreign,
            f"/v1/games/{identifier}/answer",
            answer_body(created["current_round"]),
            "foreign-answer-key-01",
        ).status_code
        == 404
    )
    assert (
        post(
            foreign,
            f"/v1/games/{identifier}/advance",
            {
                "answered_round_id": created["current_round"]["round_id"],
                "expected_revision": created["revision"],
            },
            "foreign-advance-key-1",
        ).status_code
        == 404
    )


def test_out_of_order_unknown_choices_early_results_and_premature_next_fail(gameplay, owned_seed, db_engine):
    client, owner, _ = gameplay()
    created = create(client, owned_seed(owner)).json()
    identifier, current = created["game_id"], created["current_round"]
    assert client.get(f"/v1/games/{identifier}/results").status_code == 409
    assert (
        post(
            client,
            f"/v1/games/{identifier}/advance",
            {"answered_round_id": current["round_id"], "expected_revision": current["revision"]},
            "premature-next-key-01",
        ).status_code
        == 409
    )
    unknown_round = {**answer_body(current), "round_id": str(uuid4())}
    unknown_choice = {**answer_body(current), "choice_id": str(uuid4())}
    for index, body in enumerate((unknown_round, unknown_choice)):
        assert post(
            client, f"/v1/games/{identifier}/answer", body, f"unknown-answer-{index:04d}"
        ).status_code in (404, 409)
    assert counts(db_engine, owner, identifier)["answers"] == 0


def test_known_private_future_choice_and_pair_ids_cannot_be_guessed(gameplay, owned_seed, db_engine):
    client, owner, _ = gameplay()
    created = create(client, owned_seed(owner)).json()
    identifier, current = created["game_id"], created["current_round"]
    with scoped_session(db_engine, owner) as db:
        future = db.scalar(
            select(m.PrivatePair).where(
                m.PrivatePair.game_id == UUID(identifier), m.PrivatePair.planned_ordinal == 2
            )
        )
        future_pair, future_choice = str(future.id), str(future.left_choice_id)
    requests = (
        {**answer_body(current), "choice_id": future_choice},
        {**answer_body(current), "round_id": future_pair, "choice_id": future_choice},
    )
    for index, body in enumerate(requests):
        response = post(client, f"/v1/games/{identifier}/answer", body, f"future-guess-key-{index:04d}")
        assert response.status_code == 404
        assert "winning_choice_id" not in response.text and "correct" not in response.text
    assert counts(db_engine, owner, identifier)["answers"] == 0


def test_duplicate_alias_answer_key_is_bound_and_cannot_be_reused_with_changed_input(gameplay, owned_seed):
    client, owner, _ = gameplay()
    created = create(client, owned_seed(owner)).json()
    identifier, current = created["game_id"], created["current_round"]
    body = answer_body(current)
    assert post(client, f"/v1/games/{identifier}/answer", body, "original-answer-key-1").status_code == 200
    alias = post(client, f"/v1/games/{identifier}/answer", body, "alias-answer-key-0001")
    assert alias.status_code == 200
    changed = {**body, "expected_revision": body["expected_revision"] + 1}
    assert post(client, f"/v1/games/{identifier}/answer", changed, "alias-answer-key-0001").status_code == 409


def test_duplicate_alias_next_key_is_bound_and_cannot_be_reused_with_changed_input(gameplay, owned_seed):
    client, owner, _ = gameplay()
    created = create(client, owned_seed(owner)).json()
    identifier = created["game_id"]
    reveal = post(
        client,
        f"/v1/games/{identifier}/answer",
        answer_body(created["current_round"]),
        "alias-next-answer-01",
    ).json()
    body = next_body(reveal)
    first = post(client, f"/v1/games/{identifier}/advance", body, "original-advance-key1")
    alias = post(client, f"/v1/games/{identifier}/advance", body, "alias-advance-key-001")
    assert first.status_code == 200 and alias.status_code == 200
    assert alias.json() == first.json()
    changed = {**body, "expected_revision": body["expected_revision"] + 1}
    assert (
        post(client, f"/v1/games/{identifier}/advance", changed, "alias-advance-key-001").status_code == 409
    )


def test_expired_game_rejects_all_read_and_mutation_paths(gameplay, owned_seed, db_engine):
    client, owner, _ = gameplay()
    created = create(client, owned_seed(owner)).json()
    identifier = created["game_id"]
    # Shorten retention through the permitted revisioned transition, then let it
    # actually expire; immutable creation timestamps and database clocks stay real.
    with scoped_session(db_engine, owner) as db:
        db.execute(
            update(m.Game)
            .where(m.Game.id == UUID(identifier))
            .values(
                expires_at=datetime.now(UTC) + timedelta(milliseconds=100),
                revision=m.Game.revision + 1,
            )
        )
    time.sleep(0.12)
    for suffix in ("", "/round", "/generation", "/results"):
        assert client.get(f"/v1/games/{identifier}{suffix}").status_code == 410
    assert (
        post(
            client,
            f"/v1/games/{identifier}/answer",
            answer_body(created["current_round"]),
            "expired-answer-key-01",
        ).status_code
        == 410
    )


def test_public_generation_and_reveals_never_include_future_contestants_or_private_receipt(
    gameplay, owned_seed
):
    client, owner, curator = gameplay()
    created = create(client, owned_seed(owner)).json()
    identifier = created["game_id"]
    current_names = {choice["entity"]["name"] for choice in created["current_round"]["choices"]}
    all_names = {
        candidate.name for pair in curator.outcomes[0].pool.pairs for candidate in (pair.first, pair.second)
    }
    forbidden = all_names - current_names
    payloads = [created]
    for suffix in ("/generation", "", "/round", "/results"):
        response = client.get(f"/v1/games/{identifier}{suffix}")
        payloads.append(response.json())
    reveal = post(
        client,
        f"/v1/games/{identifier}/answer",
        answer_body(created["current_round"]),
        "secrecy-answer-key-01",
    )
    assert reveal.status_code == 200
    payloads += [reveal.json(), game(client, identifier)]
    rendered = json.dumps(payloads)
    for name in forbidden:
        assert name not in rendered
    for marker in (
        "full_receipt",
        "policy_fingerprint",
        "action_trace",
        "final_feedback",
        "query_context_hash",
        "affinity",
        "snapshot_id",
        "rejection_counts",
        "candidate_count_received",
    ):
        assert marker not in rendered
