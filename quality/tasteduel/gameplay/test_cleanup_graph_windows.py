"""Real PostgreSQL regression for independent bounded cleanup graph windows."""

from datetime import UTC, datetime, timedelta
import hashlib
import importlib
import itertools
import time
from uuid import UUID

from sqlalchemy import text

from tasteduel import operations

from .test_authoritative_flow import post
from .test_challenges import complete, shared


def test_expired_duel_outside_first_hundred_owners_cannot_revive_when_edges_are_removed(
        gameplay, owned_seed, db_owner_engine, monkeypatch):
    # The synthetic duel sorts after 100 new idle owners but before historical
    # random-UUID fixtures. No production batch limit or clock hook is changed.
    base = time.time_ns()
    identifiers = itertools.count(base + 1001)
    monkeypatch.setattr(importlib.import_module("tasteduel.api.main"), "uuid4", lambda: UUID(int=next(identifiers)))
    creator, owner, _, source, reveals, invitation = shared(gameplay, owned_seed)
    friend, guest, _ = gameplay()
    replay = post(friend, f"/v1/challenges/{invitation['invitation']['slug']}/plays", {}, "graph-window-completed-play").json()
    complete(friend, replay, expected=reveals)
    # A second live friend is independent of this completed duel and must keep
    # their nickname/session. Its source is also protected by an active replay.
    live_creator, live_owner, _, _, _, live_invitation = shared(gameplay, owned_seed)
    live_friend, live_guest, _ = gameplay()
    live_replay = post(live_friend, f"/v1/challenges/{live_invitation['invitation']['slug']}/plays", {}, "graph-window-live-play").json()
    with db_owner_engine.connect() as db:
        transaction = db.begin()
        try:
            now = datetime.now(UTC)
            # All setup changes, including the test-only result ageing policy,
            # are rolled back. Existing local data remains intact.
            db.execute(text("ALTER TABLE tasteduel.game_results DISABLE TRIGGER immutable_record"))
            db.execute(text("CREATE POLICY fixture_age_graph_window ON tasteduel.game_results FOR UPDATE TO tasteduel_migrator USING(true) WITH CHECK(true)"))
            db.execute(text("UPDATE tasteduel.game_results SET created_at=clock_timestamp()-interval '11 minutes' WHERE game_id=:game"),
                       {"game": UUID(replay["game_id"])})
            db.execute(text("ALTER TABLE tasteduel.game_results ENABLE TRIGGER immutable_record"))
            for number in range(1, 101):
                identifier = UUID(int=base + number)
                db.execute(text("SELECT set_config('app.session_id',:owner,true)"), {"owner": str(identifier)})
                db.execute(text("""INSERT INTO tasteduel.sessions(id,token_hash,display_name,created_at,last_activity_at,expires_at)
                    VALUES(:owner,:token,'Idle fixture',:created,:created,:expires)"""),
                    {"owner": identifier, "token": hashlib.sha256(f"cleanup-graph-window-{base}-{number}".encode()).hexdigest(),
                     "created": now-timedelta(hours=2), "expires": now+timedelta(hours=20)})
            first_owners = list(db.execute(text("SELECT id FROM tasteduel.sessions WHERE NOT tasteduel.session_live(id) ORDER BY id LIMIT 100")).scalars())
            assert len(first_owners) == 100 and owner not in first_owners and guest not in first_owners
            for participant in (owner, guest):
                assert not db.execute(text("SELECT tasteduel.session_live(:owner)"), {"owner": participant}).scalar_one()
            operations.purge(db, execute=True)
            assert db.execute(text("SELECT count(*) FROM tasteduel.challenge_plays WHERE game_id=:game"),
                              {"game": UUID(replay["game_id"])}).scalar_one() == 0
            assert db.execute(text("SELECT count(*) FROM tasteduel.challenges WHERE source_game_id=:game"),
                              {"game": UUID(source["game_id"])}).scalar_one() == 0
            # Both rows are outside the deletion-owner window and still exist;
            # their persisted revocation prevents the fallback from reviving them.
            for participant in (owner, guest):
                row = db.execute(text("SELECT revoked_at,tasteduel.session_live(id) FROM tasteduel.sessions WHERE id=:owner"),
                                 {"owner": participant}).one()
                assert row.revoked_at is not None and row[1] is False
            for participant in (live_owner, live_guest):
                assert db.execute(text("SELECT revoked_at IS NULL AND tasteduel.session_live(id) FROM tasteduel.sessions WHERE id=:owner"),
                                  {"owner": participant}).scalar_one()
            assert db.execute(text("SELECT count(*) FROM tasteduel.challenge_plays WHERE game_id=:game"),
                              {"game": UUID(live_replay["game_id"])}).scalar_one() == 1
        finally:
            transaction.rollback()
