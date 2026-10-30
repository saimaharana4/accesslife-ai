"""Real row-policy boundaries under authenticated, transaction-local scope."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from tasteduel.persistence import models as m
from tasteduel.persistence.db import scoped_session

from ._seed import seed_private_graph


def test_private_graph_is_invisible_to_another_scope_and_to_a_reused_unscoped_connection(
    create_guest,
    db_owner_engine,
    db_engine,
):
    _, owner_id = create_guest()
    _, stranger_id = create_guest()
    graph = seed_private_graph(db_owner_engine, owner_id, answered=True)
    private_ids = (
        ("games", graph.game_id),
        ("ranking_snapshots", graph.snapshot_id),
        ("private_pairs", graph.first_pair_id),
        ("delivered_rounds", graph.first_round_id),
    )
    with db_engine.connect() as connection:
        with connection.begin():
            connection.execute(
                text("SELECT set_config('app.session_id', :owner, true)"), {"owner": str(owner_id)}
            )
            for table, record_id in private_ids:
                assert (
                    connection.execute(
                        text(f"SELECT count(*) FROM tasteduel.{table} WHERE id = :id"),
                        {"id": record_id},
                    ).scalar_one()
                    == 1
                )
        # Deliberately keep the same pooled connection. A prior caller's local
        # setting must not become the next caller's identity after commit.
        with connection.begin():
            assert connection.execute(
                text("SELECT current_setting('app.session_id', true)")
            ).scalar_one() in {None, ""}
            for table, record_id in private_ids:
                assert (
                    connection.execute(
                        text(f"SELECT count(*) FROM tasteduel.{table} WHERE id = :id"),
                        {"id": record_id},
                    ).scalar_one()
                    == 0
                )
        with connection.begin():
            connection.execute(
                text("SELECT set_config('app.session_id', :owner, true)"), {"owner": str(stranger_id)}
            )
            for table, record_id in private_ids:
                assert (
                    connection.execute(
                        text(f"SELECT count(*) FROM tasteduel.{table} WHERE id = :id"),
                        {"id": record_id},
                    ).scalar_one()
                    == 0
                )
            for table in ("answers", "curation_receipts", "provider_cache"):
                assert (
                    connection.execute(
                        text(f"SELECT count(*) FROM tasteduel.{table} WHERE session_id = :owner"),
                        {"owner": owner_id},
                    ).scalar_one()
                    == 0
                )


def test_runtime_cannot_insert_another_owners_record(create_guest, db_owner_engine, db_engine):
    _, owner_id = create_guest()
    _, stranger_id = create_guest()
    graph = seed_private_graph(db_owner_engine, owner_id)
    with pytest.raises(DBAPIError) as failure:
        with scoped_session(db_engine, stranger_id) as db:
            db.add(m.Discovery(session_id=owner_id, entity_id=graph.seed_id))
            db.flush()
    assert failure.value.orig.sqlstate == "42501"


def test_runtime_cannot_reassign_an_owned_graph_to_another_session(
    create_guest,
    db_owner_engine,
    db_engine,
):
    _, owner_id = create_guest()
    _, stranger_id = create_guest()
    graph = seed_private_graph(db_owner_engine, owner_id)
    with pytest.raises(DBAPIError):
        with scoped_session(db_engine, owner_id) as db:
            db.execute(
                text("UPDATE tasteduel.games SET session_id = :other WHERE id = :game"),
                {"other": stranger_id, "game": graph.game_id},
            )
    with scoped_session(db_engine, owner_id) as db:
        assert db.get(m.Game, graph.game_id).session_id == owner_id
    with scoped_session(db_engine, stranger_id) as db:
        assert db.get(m.Game, graph.game_id) is None


def test_database_rejects_duplicate_accepted_answers_even_with_a_new_request_key(
    create_guest,
    db_owner_engine,
    db_engine,
):
    _, owner_id = create_guest()
    graph = seed_private_graph(db_owner_engine, owner_id, answered=True)
    with pytest.raises(DBAPIError):
        with scoped_session(db_engine, owner_id) as db:
            db.add(
                m.Answer(
                    id=uuid4(),
                    session_id=owner_id,
                    game_id=graph.game_id,
                    round_id=graph.first_round_id,
                    choice_id=graph.first_right_choice_id,
                    idempotency_key="second-attempt-cannot-add-a-point",
                    correct=True,
                )
            )
            db.flush()
    with scoped_session(db_engine, owner_id) as db:
        assert (
            db.execute(
                text("SELECT count(*) FROM tasteduel.answers WHERE round_id = :round"),
                {"round": graph.first_round_id},
            ).scalar_one()
            == 1
        )
        assert (
            db.execute(
                text("SELECT correct FROM tasteduel.answers WHERE round_id = :round"),
                {"round": graph.first_round_id},
            ).scalar_one()
            is False
        )


def test_runtime_cannot_restore_a_revoked_session_or_replace_its_token_hash(
    create_guest,
    db_owner_engine,
    db_engine,
):
    client, owner_id = create_guest()
    graph = seed_private_graph(db_owner_engine, owner_id)
    with pytest.raises(DBAPIError) as failure:
        with scoped_session(db_engine, owner_id) as db:
            db.execute(
                text("UPDATE tasteduel.sessions SET token_hash = :hash WHERE id = :owner"),
                {"hash": "a" * 64, "owner": owner_id},
            )
    assert failure.value.orig.sqlstate == "42501"
    assert client.delete("/v1/sessions/current").status_code == 204
    with pytest.raises(DBAPIError):
        with scoped_session(db_engine, owner_id) as db:
            db.execute(
                text("UPDATE tasteduel.sessions SET revoked_at = NULL WHERE id = :owner"), {"owner": owner_id}
            )
    with scoped_session(db_engine, owner_id) as db:
        assert db.get(m.Session, owner_id).revoked_at is not None
        assert db.get(m.Game, graph.game_id) is None
