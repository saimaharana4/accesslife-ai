"""Production operations against real local PostgreSQL; no cloud/provider calls."""

from datetime import UTC, datetime, timedelta
import hashlib
import importlib
import itertools
import json
import time
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from tasteduel import operations as ops
from tasteduel.persistence import models as m
from tasteduel.persistence.db import scoped_session

from .test_authoritative_flow import create, post
from .test_challenges import shared

_session_ids = itertools.count(time.time_ns())


@pytest.fixture(autouse=True)
def bounded_priority_sessions(monkeypatch):
    # Fixed synthetic UUIDs put this test's owners before historic local fixtures
    # in the real bounded purge, without raising its production batch limit.
    # Request IDs also use this test-only seam; production uses uuid4 unchanged.
    module = importlib.import_module("tasteduel.api.main")
    monkeypatch.setattr(module, "uuid4", lambda: UUID(int=next(_session_ids)))


def test_purge_dryrun_and_revoked_session_preserves_active_guest(gameplay, owned_seed, db_owner_engine, db_engine):
    revoked, owner, _ = gameplay()
    game = create(revoked, owned_seed(owner)).json()
    active, active_owner, _ = gameplay()
    active_game = create(active, owned_seed(active_owner)).json()
    assert revoked.delete("/v1/sessions/current").status_code == 204
    with db_owner_engine.begin() as db:
        before = db.execute(text("SELECT count(*) FROM tasteduel.games WHERE id=:id"), {"id": UUID(game["game_id"])}).scalar_one()
        assert before == 1
        facts = ops.purge(db)
        assert facts["executed"] is False
        assert db.execute(text("SELECT count(*) FROM tasteduel.games WHERE id=:id"), {"id": UUID(game["game_id"])}).scalar_one() == 1
        result = ops.purge(db, execute=True)
        assert result["executed"] is True and result["backups_rewritten"] is False
        assert db.execute(text("SELECT count(*) FROM tasteduel.games WHERE id=:id"), {"id": UUID(game["game_id"])}).scalar_one() == 0
        assert db.execute(text("SELECT count(*) FROM tasteduel.sessions WHERE id=:id"), {"id": owner}).scalar_one() == 0
        assert db.execute(text("SELECT count(*) FROM tasteduel.games WHERE id=:id"), {"id": UUID(active_game["game_id"])}).scalar_one() == 1
    assert active.get(f"/v1/games/{active_game['game_id']}").status_code == 200
    with db_engine.begin() as db:
        with pytest.raises(ops.OperationBlocked, match="MIGRATION_IDENTITY"):
            ops.purge(db, execute=True)
    with scoped_session(db_engine, active_owner) as db:
        assert db.get(m.Game, UUID(active_game["game_id"])) is not None


def test_cross_owner_revoked_replay_purges_as_unit_and_known_link_stays_410(
        gameplay, owned_seed, db_owner_engine):
    creator, _, _, source, _, invitation = shared(gameplay, owned_seed)
    slug = invitation["invitation"]["slug"]
    guest, _, _ = gameplay()
    replay = post(guest, f"/v1/challenges/{slug}/plays", {}, "ops-replay-key-00000001").json()
    other, other_owner, _ = gameplay()
    active = create(other, owned_seed(other_owner)).json()
    with db_owner_engine.begin() as db:
        # Active fixed replays and their source survive maintenance unchanged.
        ops.purge(db, execute=True)
        assert db.execute(text("SELECT count(*) FROM tasteduel.challenge_plays WHERE game_id=:game"),
                          {"game": UUID(replay["game_id"])}).scalar_one() == 1
    assert creator.delete(f"/v1/challenges/{slug}").status_code == 204
    with db_owner_engine.begin() as db:
        ops.purge(db, execute=True)
        assert db.execute(text("SELECT count(*) FROM tasteduel.games WHERE id=:game"),
                          {"game": UUID(replay["game_id"])}).scalar_one() == 0
        assert db.execute(text("SELECT count(*) FROM tasteduel.challenge_plays WHERE game_id=:game"),
                          {"game": UUID(replay["game_id"])}).scalar_one() == 0
        assert db.execute(text("SELECT count(*) FROM tasteduel.games WHERE id=:game"),
                          {"game": UUID(source["game_id"])}).scalar_one() == 1
        tombstone = db.execute(text("SELECT slug_hash,reason,created_at,expires_at FROM tasteduel.challenge_tombstones WHERE slug_hash=:hash"),
                              {"hash": hashlib.sha256(slug.encode()).hexdigest()}).mappings().one()
        assert tombstone["reason"] == "revoked"
        assert tombstone["expires_at"]-tombstone["created_at"] <= timedelta(days=7, minutes=1)
        assert db.execute(text("SELECT count(*) FROM tasteduel.challenge_rounds WHERE challenge_id IN(SELECT id FROM tasteduel.challenges WHERE slug_hash=:hash)"),
                          {"hash": tombstone["slug_hash"]}).scalar_one() == 0
    assert guest.get(f"/v1/challenges/{slug}").status_code == 410
    assert guest.get(f"/v1/games/{replay['game_id']}").status_code == 404
    assert other.get(f"/v1/games/{active['game_id']}").status_code == 200


def test_expired_cache_removed_active_payload_and_immutable_rows_preserved(gameplay, owned_seed, db_owner_engine, db_engine):
    _, owner, _ = gameplay()
    now = datetime.now(UTC)
    with scoped_session(db_engine, owner) as db:
        for expired in (True, False):
            db.add(m.ProviderCache(session_id=owner, provider="fixture", key_hash=hashlib.sha256(str(expired).encode()).hexdigest(),
                payload={"synthetic": True}, rights_policy="project_owned", created_at=now-timedelta(hours=2),
                expires_at=now+timedelta(hours=-1 if expired else 1)))
    with db_owner_engine.begin() as db:
        ops.purge(db, execute=True)
        assert db.execute(text("SELECT count(*) FROM tasteduel.provider_cache WHERE session_id=:owner"), {"owner": owner}).scalar_one() == 1
        assert db.execute(text("DELETE FROM tasteduel.provider_cache WHERE session_id=:owner"), {"owner": owner}).rowcount == 0


@pytest.fixture
def budget_rows(db_owner_engine):
    with db_owner_engine.connect() as db:
        transaction = db.begin()
        try:
            # Transaction-local synthetic isolation; all existing local counters
            # are restored on rollback, and this never accepts a cloud URL.
            scopes = db.execute(text("SELECT DISTINCT scope_hash FROM tasteduel.usage_budgets WHERE bucket='qloo-requests-day' OR scope_hash=:scope"),
                                {"scope": ops.VERTEX_SCOPE}).scalars().all()
            for scope in scopes:
                db.execute(text("SELECT set_config('app.usage_scope',:scope,true)"), {"scope": scope})
                db.execute(text("DELETE FROM tasteduel.usage_budgets WHERE scope_hash=:scope AND (bucket='qloo-requests-day' OR scope_hash=:vertex)"),
                           {"scope": scope, "vertex": ops.VERTEX_SCOPE})
            qloo = hashlib.sha256(uuid4().bytes).hexdigest()
            for scope, bucket, used, limit in ((ops.VERTEX_SCOPE,"vertex-requests-day",10,10),
                    (ops.VERTEX_SCOPE,"vertex-tokens-day",21000,500000),(qloo,"qloo-requests-day",10,12)):
                db.execute(text("SELECT set_config('app.usage_scope',:scope,true)"), {"scope": scope})
                db.execute(text("""INSERT INTO tasteduel.usage_budgets(scope_hash,bucket,used,limit_value,window_start,expires_at)
                    VALUES(:scope,:bucket,:used,:limit,clock_timestamp()-interval '1 hour',clock_timestamp()+interval '1 hour')"""),
                    {"scope": scope, "bucket": bucket, "used": used, "limit": limit})
            yield db
        finally:
            transaction.rollback()


def test_public_budget_is_fixed_preserves_usage_dates_and_tokens(budget_rows):
    db = budget_rows
    before = ops.budget_snapshot(db)
    inspection = ops.promote_budget(db)
    assert "scope_hash" not in json.dumps(inspection)
    result = ops.promote_budget(db, execute=True, expected_digest=inspection["snapshot_sha256"])
    assert result["usage_reset"] is False and result["window_extended"] is False
    after = ops.budget_snapshot(db)
    assert after["vertex-tokens-day"] == before["vertex-tokens-day"]
    for bucket, limit in (("vertex-requests-day",50),("qloo-requests-day",100)):
        assert after[bucket] == {**before[bucket],"limit_value":limit}
    with pytest.raises(ops.OperationBlocked, match="EXACT_PROVIDER_SNAPSHOT"):
        ops.promote_budget(db, execute=True, expected_digest=inspection["snapshot_sha256"])


@pytest.mark.parametrize("changed", ["used", "expiry", "ambiguous"])
def test_public_budget_mismatches_never_widen_rows(budget_rows, changed):
    db = budget_rows
    expected = ops.promote_budget(db)["snapshot_sha256"]
    if changed == "used":
        db.execute(text("UPDATE tasteduel.usage_budgets SET used=9 WHERE bucket='vertex-requests-day' AND scope_hash=:scope"), {"scope": ops.VERTEX_SCOPE})
    elif changed == "expiry":
        db.execute(text("UPDATE tasteduel.usage_budgets SET window_start=clock_timestamp()-interval '2 hour',expires_at=clock_timestamp()-interval '1 hour' WHERE scope_hash=:scope AND bucket='vertex-requests-day'"), {"scope": ops.VERTEX_SCOPE})
    else:
        scope = hashlib.sha256(uuid4().bytes).hexdigest()
        db.execute(text("SELECT set_config('app.usage_scope',:scope,true)"), {"scope": scope})
        db.execute(text("""INSERT INTO tasteduel.usage_budgets(scope_hash,bucket,used,limit_value,window_start,expires_at)
            VALUES(:scope,'qloo-requests-day',10,12,clock_timestamp(),clock_timestamp()+interval '1 hour')"""), {"scope": scope})
    with pytest.raises(ops.OperationBlocked):
        ops.promote_budget(db, execute=True, expected_digest=expected)
    assert db.execute(text("SELECT limit_value FROM tasteduel.usage_budgets WHERE bucket='vertex-requests-day' AND scope_hash=:scope"),
                      {"scope": ops.VERTEX_SCOPE}).scalar_one() == 10


def test_runtime_cannot_use_maintenance_policy_or_tombstone_enumeration(gameplay, owned_seed, db_engine):
    _, owner, _ = gameplay()
    with scoped_session(db_engine, owner) as db:
        assert db.execute(text("SELECT count(*) FROM tasteduel.challenge_tombstones")).scalar_one() == 0
        for statement in ("SELECT tasteduel.maintenance_deletable('sessions','{}'::jsonb)",
                          "INSERT INTO tasteduel.challenge_tombstones VALUES('"+"a"*64+"','expired',clock_timestamp(),clock_timestamp()+interval '1 day')"):
            nested = db.begin_nested()
            with pytest.raises(DBAPIError):
                db.execute(text(statement))
            nested.rollback()


def test_structured_events_omit_identity_search_and_private_answer(caplog):
    import logging
    caplog.set_level(logging.INFO, logger="uvicorn.error")
    ops.safe_event("generation",status=201,elapsed_ms=10,mode="genuine_agent")
    facts = json.loads(caplog.records[-1].message)
    assert facts == {"event":"generation","status":201,"elapsed_ms":10,"mode":"genuine_agent"}
    with pytest.raises(ValueError):
        ops.safe_event("synthetic-private-query",status=201,elapsed_ms=1)


def test_reviewed_mutation_requires_matching_hash_and_finite_horizon(monkeypatch):
    monkeypatch.setenv("TASTEDUEL_OPS_COST_REVIEW_HASH","a"*64)
    monkeypatch.setenv("TASTEDUEL_OPS_REVIEWED_THROUGH_UTC","2026-11-07T04:45:00Z")
    ops.reviewed_mutation("a"*64)
    with pytest.raises(ops.OperationBlocked):
        ops.reviewed_mutation("b"*64)
    monkeypatch.setenv("TASTEDUEL_OPS_REVIEWED_THROUGH_UTC","2030-01-01T00:00:00Z")
    with pytest.raises(ops.OperationBlocked):
        ops.reviewed_mutation("a"*64)


def test_readiness_budget_metadata_does_not_invoke_providers(budget_rows, db_engine):
    rows = ops.budget_snapshot(budget_rows)
    qloo = rows["qloo-requests-day"]["scope_hash"]
    # Use this transaction's connection rather than a transport/provider client.
    class Engine:
        def begin(self):
            from contextlib import nullcontext
            return nullcontext(budget_rows)
    assert ops.admission_available(Engine(),qloo_scope=qloo,project=ops.PROJECT,model=ops.MODEL,
                                  qloo_limit=12,model_limit=10,token_limit=500000) is False
    assert ops.admission_available(Engine(),qloo_scope=qloo,project=ops.PROJECT,model=ops.MODEL,
                                  qloo_limit=100,model_limit=50,token_limit=500000) is False
