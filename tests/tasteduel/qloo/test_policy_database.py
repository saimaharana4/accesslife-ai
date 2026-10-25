"""Real dedicated Taste Duel PostgreSQL admission, across separate store instances."""

import asyncio
from contextlib import contextmanager
import hashlib
import time
from uuid import uuid4

import pytest
from sqlalchemy import text

from tasteduel.adapters.qloo_policy import AdmissionDenied, PostgresAdmissionStore


@pytest.fixture
def provider_scope(db_owner_engine):
    scope = hashlib.sha256(uuid4().bytes).hexdigest()
    yield scope
    with scope_connection(db_owner_engine, scope) as db:
        db.execute(text("DELETE FROM tasteduel.provider_controls WHERE scope_hash=:scope"), {"scope": scope})


@contextmanager
def scope_connection(engine, scope):
    with engine.begin() as db:
        db.execute(text("SELECT set_config('app.provider_scope', :scope, true)"), {"scope": scope})
        yield db


def clear_spacing(engine, scope):
    with scope_connection(engine, scope) as db:
        db.execute(
            text("""UPDATE tasteduel.provider_controls
            SET next_allowed_at=clock_timestamp()-interval '1 second' WHERE scope_hash=:scope"""),
            {"scope": scope},
        )


async def test_two_instances_share_atomic_admission_instead_of_each_having_a_local_bucket(
    db_engine, provider_scope
):
    first = PostgresAdmissionStore(db_engine, requests_per_minute=1, spacing_seconds=0.05)
    second = PostgresAdmissionStore(db_engine, requests_per_minute=1, spacing_seconds=0.05)
    results = await asyncio.gather(
        first.admit(provider_scope), second.admit(provider_scope), return_exceptions=True
    )
    assert sum(result is None for result in results) == 1
    denied = [result for result in results if isinstance(result, AdmissionDenied)]
    assert [result.code for result in denied] == ["QLOO_SHARED_RATE_LIMIT"]
    with scope_connection(db_engine, provider_scope) as db:
        assert (
            db.execute(
                text("SELECT used FROM tasteduel.provider_controls WHERE scope_hash=:scope"),
                {"scope": provider_scope},
            ).scalar_one()
            == 1
        )


async def test_independent_instances_serialize_spacing_before_admitting(db_engine, provider_scope):
    first = PostgresAdmissionStore(db_engine, spacing_seconds=1)
    second = PostgresAdmissionStore(db_engine, spacing_seconds=1)

    async def observe(store):
        await store.admit(provider_scope)
        return time.monotonic()

    admitted = sorted(await asyncio.gather(observe(first), observe(second)))
    assert admitted[1] - admitted[0] >= 0.8
    with scope_connection(db_engine, provider_scope) as db:
        assert (
            db.execute(
                text("SELECT used FROM tasteduel.provider_controls WHERE scope_hash=:scope"),
                {"scope": provider_scope},
            ).scalar_one()
            == 2
        )


async def test_higher_instance_limit_cannot_raise_persisted_lower_limit(db_engine, provider_scope):
    conservative = PostgresAdmissionStore(db_engine, requests_per_minute=1)
    permissive = PostgresAdmissionStore(db_engine, requests_per_minute=120)
    await conservative.admit(provider_scope)
    clear_spacing(db_engine, provider_scope)
    with pytest.raises(AdmissionDenied, match="QLOO_SHARED_RATE_LIMIT"):
        await permissive.admit(provider_scope)
    with scope_connection(db_engine, provider_scope) as db:
        assert tuple(
            db.execute(
                text("SELECT used,limit_value FROM tasteduel.provider_controls WHERE scope_hash=:scope"),
                {"scope": provider_scope},
            ).one()
        ) == (1, 1)


async def test_circuit_and_auth_blocks_are_shared_and_auth_is_sticky(db_engine, provider_scope):
    first, second = PostgresAdmissionStore(db_engine), PostgresAdmissionStore(db_engine)
    for _ in range(3):
        await first.record(provider_scope, failed=True)
    with pytest.raises(AdmissionDenied, match="QLOO_CIRCUIT_OPEN"):
        await second.admit(provider_scope)
    with scope_connection(db_engine, provider_scope) as db:
        db.execute(
            text("""UPDATE tasteduel.provider_controls SET open_until=clock_timestamp()-interval '1 second'
            WHERE scope_hash=:scope"""),
            {"scope": provider_scope},
        )
    await second.admit(provider_scope)
    await second.record(provider_scope, failed=False)
    await first.record(provider_scope, failed=False, auth=True)
    clear_spacing(db_engine, provider_scope)
    with pytest.raises(AdmissionDenied, match="QLOO_AUTHENTICATION_FAILED"):
        await second.admit(provider_scope)
    await first.record(provider_scope, failed=False)
    with pytest.raises(AdmissionDenied, match="QLOO_AUTHENTICATION_FAILED"):
        await second.admit(provider_scope)


async def test_rls_hides_control_rows_without_matching_key_scope(db_engine, provider_scope):
    store = PostgresAdmissionStore(db_engine)
    await store.admit(provider_scope)
    other = hashlib.sha256(uuid4().bytes).hexdigest()
    with db_engine.begin() as db:
        assert db.execute(text("SELECT count(*) FROM tasteduel.provider_controls")).scalar_one() == 0
    with scope_connection(db_engine, other) as db:
        assert (
            db.execute(
                text("SELECT count(*) FROM tasteduel.provider_controls WHERE scope_hash=:scope"),
                {"scope": provider_scope},
            ).scalar_one()
            == 0
        )
        assert (
            db.execute(
                text("UPDATE tasteduel.provider_controls SET used=0 WHERE scope_hash=:scope"),
                {"scope": provider_scope},
            ).rowcount
            == 0
        )
    with scope_connection(db_engine, provider_scope) as db:
        assert (
            db.execute(
                text("SELECT used FROM tasteduel.provider_controls WHERE scope_hash=:scope"),
                {"scope": provider_scope},
            ).scalar_one()
            == 1
        )


async def test_expired_minute_window_resets_counter_but_keeps_lower_limit(db_engine, provider_scope):
    store = PostgresAdmissionStore(db_engine, requests_per_minute=1)
    await store.admit(provider_scope)
    with scope_connection(db_engine, provider_scope) as db:
        db.execute(
            text("""UPDATE tasteduel.provider_controls
            SET window_start=clock_timestamp()-interval '61 seconds', next_allowed_at=NULL
            WHERE scope_hash=:scope"""),
            {"scope": provider_scope},
        )
    await PostgresAdmissionStore(db_engine, requests_per_minute=120).admit(provider_scope)
    with scope_connection(db_engine, provider_scope) as db:
        assert tuple(
            db.execute(
                text("SELECT used,limit_value FROM tasteduel.provider_controls WHERE scope_hash=:scope"),
                {"scope": provider_scope},
            ).one()
        ) == (1, 1)
