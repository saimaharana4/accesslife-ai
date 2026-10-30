"""Accounting records authority once, stays private and never infers preference."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, IntegrityError

from tasteduel.application.event_accounting import record
from tasteduel.persistence import models as m
from tasteduel.persistence.db import scoped_session

from .test_authoritative_flow import answer_body, create, post
from .test_challenges import complete, shared


def rows(engine, owner):
    with scoped_session(engine, owner) as db:
        return list(db.scalars(select(m.ProductEvent)))


def test_full_flow_and_fixed_replay_account_once_without_private_payloads(gameplay, owned_seed, db_engine):
    creator, owner, _, source, _, invitation = shared(gameplay, owned_seed)
    original = rows(db_engine, owner)
    assert [row.event for row in original].count("round_answered") == 5
    assert {row.event for row in original} == {"game_started", "round_answered", "game_completed", "challenge_create"}
    assert all(row.source_mode == "fixture" and row.cohort == "excluded" for row in original)
    assert set(m.ProductEvent.__table__.columns.keys()) == {
        "id", "session_id", "game_id", "subject_id", "event", "source_mode", "cohort", "created_at", "expires_at"
    }
    post(creator, "/v1/challenges", {"game_id": source["game_id"]}, "challenge-create-key-0001")
    assert len(rows(db_engine, owner)) == len(original)
    guest, guest_id, curator = gameplay()
    slug = invitation["invitation"]["slug"]
    # Public preview fetches are not counted as qualified opens (bots/prefetch).
    guest.get(f"/v1/challenges/{slug}")
    assert rows(db_engine, guest_id) == []
    replay = post(guest, f"/v1/challenges/{slug}/plays", {}, "accounting-play-key-001").json()
    post(guest, f"/v1/challenges/{slug}/plays", {}, "accounting-play-key-001")
    complete(guest, replay)
    replay_events = rows(db_engine, guest_id)
    assert len(replay_events) == 10
    assert {row.event for row in replay_events} == {
        "game_started", "replay", "challenge_open", "round_answered", "game_completed", "challenge_complete"
    }
    assert curator.calls == 0
    with scoped_session(db_engine, guest_id) as db:
        assert not list(db.scalars(select(m.ProductEvent).where(m.ProductEvent.session_id == owner)))
    assert guest.delete("/v1/sessions/current").status_code == 204
    assert rows(db_engine, guest_id) == []


def test_accepted_answer_retry_and_explicit_save_are_distinct(gameplay, owned_seed, db_engine):
    client, owner, _ = gameplay()
    client.headers["TASTEDUEL_EVENT_COHORT"] = "operational"
    game = create(client, owned_seed(owner)).json()
    path = f"/v1/games/{game['game_id']}/answer"
    body = answer_body(game["current_round"])
    reveal = post(client, path, body, "accounting-answer-key-001").json()
    assert post(client, path, body, "accounting-answer-key-001").status_code == 200
    assert len(rows(db_engine, owner)) == 2
    assert all(row.cohort == "excluded" for row in rows(db_engine, owner))
    assert not any(row.event == "discovery_saved" for row in rows(db_engine, owner))
    entity = reveal["choices"][0]["entity"]["id"]
    assert post(client, "/v1/discoveries", {"entity_id": entity}, "accounting-save-key-0001").status_code == 201
    assert post(client, "/v1/discoveries", {"entity_id": entity}, "accounting-save-key-0001").status_code == 200
    assert [row.event for row in rows(db_engine, owner)].count("discovery_saved") == 1
    with pytest.raises(IntegrityError):
        with scoped_session(db_engine, owner) as db:
            existing = rows(db_engine, owner)[0]
            db.add(m.ProductEvent(
                session_id=owner, game_id=UUID(game["game_id"]), subject_id=uuid4(),
                event="arbitrary_payload", source_mode="fixture", cohort="excluded", expires_at=existing.expires_at,
            ))
            db.flush()
    with scoped_session(db_engine, owner) as db:
        with pytest.raises(ValueError):
            record(db, owner=owner, game_id=UUID(game["game_id"]), event="secret", subject_id=uuid4())


def test_event_deduplication_transaction_rollback_expiry_and_runtime_privileges(
    gameplay, owned_seed, db_engine, monkeypatch
):
    client, owner, _ = gameplay()
    game_id = UUID(create(client, owned_seed(owner)).json()["game_id"])
    before = len(rows(db_engine, owner))
    with pytest.raises(RuntimeError):
        with scoped_session(db_engine, owner) as db:
            record(db, owner=owner, game_id=game_id, event="replay", subject_id=game_id)
            raise RuntimeError("synthetic transaction interruption")
    assert len(rows(db_engine, owner)) == before
    expired_id = uuid4()
    now = datetime.now(UTC)
    with scoped_session(db_engine, owner) as db:
        db.add(m.ProductEvent(
            session_id=owner, game_id=game_id, subject_id=expired_id,
            event="replay", source_mode="fixture", cohort="excluded",
            created_at=now - timedelta(days=8), expires_at=now - timedelta(days=1),
        ))
    monkeypatch.setenv("TASTEDUEL_EVENT_COHORT", "operational")
    with scoped_session(db_engine, owner) as db:
        for _ in range(2):
            record(db, owner=owner, game_id=game_id, event="replay", subject_id=game_id)
    result = rows(db_engine, owner)
    assert len(result) == before + 1
    assert not any(row.subject_id == expired_id for row in result)
    # Operator opting into activity cannot turn fixture data into Qloo evidence.
    assert all(row.source_mode == "fixture" for row in result)
    assert next(row for row in result if row.event == "replay").cohort == "operational"
    with pytest.raises(DBAPIError):
        with scoped_session(db_engine, owner) as db:
            db.execute(m.ProductEvent.__table__.update().values(cohort="operational"))


@pytest.mark.parametrize("mode", ["deterministic_qloo", "genuine_agent"])
def test_qloo_cohort_classification_from_synthetic_stored_receipt_only(
    gameplay, owned_seed, db_engine, monkeypatch, mode
):
    """Synthetic DB contract: no live call and absolutely no human impact evidence."""
    client, owner, _ = gameplay()
    source_id = UUID(create(client, owned_seed(owner)).json()["game_id"])
    monkeypatch.setenv("TASTEDUEL_EVENT_COHORT", "operational")
    with scoped_session(db_engine, owner) as db:
        source = db.get(m.Game, source_id)
        game = m.Game(
            session_id=owner, seed_entity_id=source.seed_entity_id, seed_type=source.seed_type,
            mode="solo", status="preparing", current_ordinal=0, revision=0,
            scoring_version=source.scoring_version, validator_version=source.validator_version,
            expires_at=source.expires_at,
        )
        db.add(game)
        db.flush()
        prior = db.scalar(select(m.CurationReceipt).where(m.CurationReceipt.game_id == source_id))
        values = {
            column.name: getattr(prior, column.name)
            for column in m.CurationReceipt.__table__.columns
            if column.name not in {"id", "session_id", "game_id", "full_receipt"}
        }
        values.update(
            curator_mode=mode, qloo_request_count=1,
            model_request_count=1 if mode == "genuine_agent" else 0,
            model_version="synthetic-contract-model" if mode == "genuine_agent" else None,
            provider_version="synthetic-classification-contract-not-live",
        )
        db.add(m.CurationReceipt(session_id=owner, game_id=game.id, **values))
        db.flush()
        record(db, owner=owner, game_id=game.id, event="game_started", subject_id=game.id)
        identifier = game.id
    contract_event = next(row for row in rows(db_engine, owner) if row.game_id == identifier)
    assert (contract_event.source_mode, contract_event.cohort) == ("qloo", "operational")
    # Contract-only mode labels must not remain in local operational reports.
    assert client.delete("/v1/sessions/current").status_code == 204
