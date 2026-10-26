"""Independent receipt authority and provider-identity isolation checks."""

from uuid import UUID

from sqlalchemy import func, select

from tasteduel.persistence import models as m
from tasteduel.persistence.db import scoped_session


def create(client, body, key="independent-security-create-key"):
    return client.post("/v1/games", json=body, headers={"Idempotency-Key": key})


def test_identical_upstream_candidate_ids_can_publish_for_two_isolated_guests(
    gameplay, owned_seed, db_engine
):
    first, first_owner, first_curator = gameplay()
    second, second_owner, second_curator = gameplay()
    response_a = create(first, owned_seed(first_owner))
    response_b = create(second, owned_seed(second_owner))
    assert response_a.status_code == response_b.status_code == 201
    assert first_curator.calls == second_curator.calls == 1
    game_a, game_b = response_a.json(), response_b.json()
    assert game_a["game_id"] != game_b["game_id"]
    internal_ids = []
    provider_ids = []
    for owner in (first_owner, second_owner):
        with scoped_session(db_engine, owner) as db:
            rows = list(
                db.scalars(
                    select(m.Entity).where(
                        m.Entity.session_id == owner,
                        m.Entity.name.like("SYNTHETIC_PRIVATE_MOVIE_%"),
                    )
                )
            )
            assert len(rows) >= 10
            internal_ids.append({row.id for row in rows})
            provider_ids.append({row.provider_entity_id for row in rows})
    assert provider_ids[0] == provider_ids[1]
    assert internal_ids[0].isdisjoint(internal_ids[1])
    for client, other_game in ((first, game_b), (second, game_a)):
        for suffix in ("", "/round", "/results", "/generation"):
            denied = client.get(f"/v1/games/{other_game['game_id']}{suffix}")
            assert denied.status_code == 404
            assert "SYNTHETIC_PRIVATE_MOVIE" not in denied.text
            assert "winning_choice_id" not in denied.text


def test_lost_create_response_retry_preserves_one_exact_private_execution_receipt(
    gameplay, owned_seed, db_engine
):
    client, owner, curator = gameplay()
    body = owned_seed(owner)
    created = create(client, body)
    assert created.status_code == 201
    game_id = UUID(created.json()["game_id"])
    with scoped_session(db_engine, owner) as db:
        receipt = db.scalar(select(m.CurationReceipt).where(m.CurationReceipt.game_id == game_id))
        identifier, full_receipt = receipt.id, receipt.full_receipt
        assert full_receipt == curator.outcomes[0].receipt.model_dump(mode="json")
        assert full_receipt["action_trace"]
        assert full_receipt["final_feedback"]["five_round_path_verified"] is True
    restarted, restarted_owner, replacement_curator = gameplay(cookie=client.cookies.get("tasteduel_session"))
    assert restarted_owner == owner
    retried = create(restarted, body)
    assert retried.status_code == 200
    assert retried.json() == created.json()
    assert curator.calls == 1
    assert replacement_curator.calls == 0
    with scoped_session(db_engine, owner) as db:
        receipts = list(db.scalars(select(m.CurationReceipt).where(m.CurationReceipt.game_id == game_id)))
        assert len(receipts) == 1
        assert receipts[0].id == identifier
        assert receipts[0].full_receipt == full_receipt
        assert (
            db.scalar(
                select(func.count())
                .select_from(m.GenerationReservation)
                .where(m.GenerationReservation.game_id == game_id)
            )
            == 1
        )
    for response in (created, retried, restarted.get(f"/v1/games/{game_id}")):
        assert "action_trace" not in response.text
        assert "evaluation_feedback" not in response.text
        assert "model_input_tokens" not in response.text
        assert "provider_version" not in response.text


def test_exhausted_generation_status_is_safe_failed_observation_with_fresh_game_recovery(
    gameplay, owned_seed, db_engine
):
    class FailingCurator:
        calls = 0

        async def curate(self, *args, **kwargs):
            self.calls += 1
            raise RuntimeError("PRIVATE_GENERATION_FAILURE_DIAGNOSTIC")

    curator = FailingCurator()
    client, owner, _ = gameplay(generator=curator)
    body = owned_seed(owner)
    key = "independent-security-three-failures"
    for expected_attempt in range(1, 4):
        failed = create(client, body, key)
        assert failed.status_code == 503
        assert "PRIVATE_GENERATION_FAILURE_DIAGNOSTIC" not in failed.text
        assert curator.calls == expected_attempt
    with scoped_session(db_engine, owner) as db:
        reservation = db.scalar(
            select(m.GenerationReservation).where(m.GenerationReservation.session_id == owner)
        )
        assert reservation.attempt_count == 3
        assert reservation.status == "failed"
        game_id = reservation.game_id
        assert (
            db.scalar(
                select(func.count())
                .select_from(m.CurationReceipt)
                .where(m.CurationReceipt.session_id == owner)
            )
            == 0
        )
    observation = client.get(f"/v1/games/{game_id}/generation")
    assert observation.status_code == 200
    assert observation.json()["status"] == "failed"
    assert observation.json()["recovery_action"] == "start_new_game"
    assert observation.json()["lease_expires_at"] is None
    assert observation.json()["retry_after_seconds"] is None
    assert set(observation.json()) == {
        "game_id",
        "status",
        "lease_expires_at",
        "retry_after_seconds",
        "recovery_action",
    }
    assert "no-store" in observation.headers["cache-control"]
    assert create(client, body, key).status_code == 503
    assert curator.calls == 3


def test_default_runtime_never_publishes_a_fixture_as_live_game(create_guest, owned_seed, db_engine):
    client, owner = create_guest()
    body = owned_seed(owner)
    response = create(client, body, key="independent-security-no-fixture-runtime")
    assert response.status_code in {422, 503}
    assert "SYNTHETIC_PRIVATE_MOVIE" not in response.text
    with scoped_session(db_engine, owner) as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(m.CurationReceipt)
                .where(m.CurationReceipt.session_id == owner)
            )
            == 0
        )
        assert (
            db.scalar(
                select(func.count()).select_from(m.DeliveredRound).where(m.DeliveredRound.session_id == owner)
            )
            == 0
        )
