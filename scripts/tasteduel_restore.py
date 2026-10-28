"""Bounded private in-memory logical rehearsal; never restore over either app DB.

No cloud connections or credentials are discovered here. An authorized operator
supplies role-specific connection factories after pricing approval. Only two
explicit active validation sessions are copied; global provider quota/cache state
without session ownership is excluded. No proprietary bytes are saved to disk.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
import io
from pathlib import Path
import re
import secrets
from uuid import UUID

from alembic import command
from alembic.config import Config
from psycopg import sql

from tasteduel.persistence.models import Base

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 8 * 1024 * 1024
MAX_ROWS_PER_TABLE_SESSION = 1000
TARGET_PATTERN = re.compile(r"^tasteduel_restore_[a-f0-9]{16}$")
TABLES = tuple(table for table in Base.metadata.sorted_tables
               if table.schema == "tasteduel" and (table.name == "sessions" or "session_id" in table.c))


class RestoreBoundaryError(RuntimeError):
    """Only fixed safe diagnostics may cross this boundary."""


@dataclass(frozen=True)
class RestoreTarget:
    name: str
    marker: str

    @classmethod
    def fresh(cls):
        return cls("tasteduel_restore_" + secrets.token_hex(8), "tasteduel-disposable:" + secrets.token_hex(16))


@dataclass(repr=False)
class MemoryBackup:
    owners: tuple[UUID, ...]
    revision: str
    expires_at: datetime
    chunks: list = field(repr=False)
    counts: dict = field(repr=False)
    byte_count: int
    digest: str


def _target(target):
    if not TARGET_PATTERN.fullmatch(target.name) or not re.fullmatch(r"tasteduel-disposable:[a-f0-9]{32}", target.marker):
        raise RestoreBoundaryError("Disposable restore identity is invalid.")


def _identity(connection, database, user):
    actual = connection.execute("SELECT current_database(),current_user").fetchone()
    if tuple(actual) != (database, user):
        raise RestoreBoundaryError("Unexpected restore database or principal.")


def render_schema_sql():
    output = io.StringIO()
    config = Config(str(ROOT / "apps/api/tasteduel-alembic.ini"), output_buffer=output)
    config.attributes["tasteduel_schema_export"] = True
    command.upgrade(config, "head", sql=True)
    return output.getvalue()


def create_target(admin_factory, migrator_factory, target):
    """Create a new exact disposable DB and schema; no adopted/existing target."""
    _target(target)
    with admin_factory("tasteduel") as admin:
        _identity(admin, "tasteduel", "accesslife")
        exists = admin.execute("SELECT 1 FROM pg_database WHERE datname=%s", (target.name,)).fetchone()
        admin.rollback()
        if exists:
            raise RestoreBoundaryError("Restore target already exists; refusing adoption.")
        admin.autocommit = True
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target.name)))
        admin.execute(sql.SQL("COMMENT ON DATABASE {} IS {}").format(sql.Identifier(target.name), sql.Literal(target.marker)))
    with admin_factory(target.name) as admin:
        _identity(admin, target.name, "accesslife")
        admin.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(target.name)))
        admin.execute(sql.SQL("GRANT CONNECT,CREATE ON DATABASE {} TO tasteduel_migrator").format(sql.Identifier(target.name)))
        admin.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO tasteduel_runtime").format(sql.Identifier(target.name)))
        admin.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC,tasteduel_runtime,tasteduel_migrator")
    with migrator_factory(target.name) as owner:
        _identity(owner, target.name, "tasteduel_migrator")
        owner.execute("CREATE SCHEMA tasteduel AUTHORIZATION tasteduel_migrator")
        owner.commit()
        # Owned static schema only. Alembic emits its own BEGIN/COMMIT boundaries.
        owner.execute(render_schema_sql())
        owner.commit()
    with admin_factory(target.name) as admin:
        _identity(admin, target.name, "accesslife")
        admin.execute(sql.SQL("REVOKE CREATE ON DATABASE {} FROM tasteduel_migrator").format(sql.Identifier(target.name)))
    return {"target_created": True, "schema_initialized": True, "managed_instance_created": False}


def export_sessions(connection, owners, *, target=None):
    """Capture one consistent, bounded owner-scoped snapshot with unexpired data."""
    owners = tuple(UUID(str(owner)) for owner in owners)
    if not 1 <= len(owners) <= 2 or len(set(owners)) != len(owners):
        raise RestoreBoundaryError("One or two distinct validation sessions are required.")
    chunks, counts, total = [], {}, 0
    digest = hashlib.sha256()
    expiries = []
    with connection.transaction():
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        if target is not None:
            _target(target)
        _identity(connection, target.name if target is not None else "tasteduel", "tasteduel_runtime")
        if target is not None and connection.execute(
            "SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()"
        ).fetchone()[0] != target.marker:
            raise RestoreBoundaryError("Unexpected verification database marker.")
        revision = connection.execute("SELECT version_num FROM tasteduel.tasteduel_alembic_version").fetchone()[0]
        for table in TABLES:
            key = "id" if table.name == "sessions" else "session_id"
            for owner in owners:
                connection.execute("SELECT set_config('app.session_id',%s,true)", (str(owner),))
                where = sql.SQL("{}=%s").format(sql.Identifier(key))
                count = connection.execute(sql.SQL("SELECT count(*) FROM tasteduel.{} WHERE ").format(sql.Identifier(table.name)) + where, (owner,)).fetchone()[0]
                if count > MAX_ROWS_PER_TABLE_SESSION or (table.name == "sessions" and count != 1):
                    raise RestoreBoundaryError("Validation snapshot scope is missing or too large.")
                if "expires_at" in table.c and count:
                    expiry = connection.execute(sql.SQL("SELECT min(expires_at) FROM tasteduel.{} WHERE ").format(sql.Identifier(table.name)) + where, (owner,)).fetchone()[0]
                    expiries.append(expiry)
                statement = sql.SQL("COPY (SELECT {} FROM tasteduel.{} WHERE ").format(
                    sql.SQL(",").join(sql.Identifier(column.name) for column in table.columns), sql.Identifier(table.name),
                ) + where + sql.SQL(" ORDER BY id) TO STDOUT (FORMAT BINARY)")
                data = bytearray()
                with connection.cursor().copy(statement, (owner,)) as copy:
                    while block := copy.read():
                        data.extend(block)
                        total += len(block)
                        if total > MAX_BYTES:
                            raise RestoreBoundaryError("Validation snapshot exceeds its byte envelope.")
                payload = bytes(data)
                digest.update(table.name.encode() + owner.bytes + payload)
                chunks.append((table.name, owner, payload))
                counts[(table.name, owner)] = count
    expires_at = min(expiries)
    if expires_at <= datetime.now(UTC):
        raise RestoreBoundaryError("Expired evidence cannot enter a restore rehearsal.")
    return MemoryBackup(owners, revision, expires_at, chunks, counts, total, digest.hexdigest())


def restore_sessions(connection, target, backup):
    """Import only into the newly marked empty target; restore RLS/trigger state."""
    _target(target)
    if backup.expires_at <= datetime.now(UTC):
        raise RestoreBoundaryError("Private rehearsal backup has expired.")
    expected = {table.name: table for table in TABLES}
    digest = hashlib.sha256()
    for name, owner, payload in backup.chunks:
        if name not in expected or owner not in backup.owners:
            raise RestoreBoundaryError("Unexpected private backup relation.")
        digest.update(name.encode() + owner.bytes + payload)
    if digest.hexdigest() != backup.digest or sum(len(item[2]) for item in backup.chunks) != backup.byte_count or backup.byte_count > MAX_BYTES:
        raise RestoreBoundaryError("Private backup integrity failed.")
    with connection.transaction():
        _identity(connection, target.name, "tasteduel_migrator")
        marker = connection.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()").fetchone()[0]
        if marker != target.marker:
            raise RestoreBoundaryError("Disposable target marker does not match.")
        revision = connection.execute("SELECT version_num FROM tasteduel.tasteduel_alembic_version").fetchone()[0]
        if revision != backup.revision:
            raise RestoreBoundaryError("Restore schema revision does not match the backup.")
        for table in TABLES:
            connection.execute(sql.SQL("ALTER TABLE tasteduel.{} DISABLE ROW LEVEL SECURITY").format(sql.Identifier(table.name)))
            connection.execute(sql.SQL("ALTER TABLE tasteduel.{} DISABLE TRIGGER USER").format(sql.Identifier(table.name)))
            if connection.execute(sql.SQL("SELECT count(*) FROM tasteduel.{}").format(sql.Identifier(table.name))).fetchone()[0]:
                raise RestoreBoundaryError("Restore target must contain no application rows.")
        for name, owner, payload in backup.chunks:
            if name not in expected or owner not in backup.owners:
                raise RestoreBoundaryError("Unexpected private backup relation.")
            table = expected[name]
            statement = sql.SQL("COPY tasteduel.{} ({}) FROM STDIN (FORMAT BINARY)").format(
                sql.Identifier(name), sql.SQL(",").join(sql.Identifier(column.name) for column in table.columns),
            )
            with connection.cursor().copy(statement) as copy:
                copy.write(payload)
        for table in TABLES:
            connection.execute(sql.SQL("ALTER TABLE tasteduel.{} ENABLE TRIGGER USER").format(sql.Identifier(table.name)))
            connection.execute(sql.SQL("ALTER TABLE tasteduel.{} ENABLE ROW LEVEL SECURITY").format(sql.Identifier(table.name)))
            connection.execute(sql.SQL("ALTER TABLE tasteduel.{} FORCE ROW LEVEL SECURITY").format(sql.Identifier(table.name)))
    return {"logical_restore_imported": True, "source_database_modified": False,
            "rls_and_user_triggers_reenabled": True, "backup_bytes_written_to_files": False}


def verify_restored(connection, target, backup):
    """Compare private bytes/counts and actual stored score/frozen-pair invariants."""
    restored = export_sessions(connection, backup.owners, target=target)
    if restored.digest != backup.digest or restored.counts != backup.counts or restored.revision != backup.revision:
        raise RestoreBoundaryError("Restored private rows differ from the consistent backup.")
    results = challenges = 0
    with connection.transaction():
        _identity(connection, target.name, "tasteduel_runtime")
        for owner in backup.owners:
            connection.execute("SELECT set_config('app.session_id',%s,true)", (str(owner),))
            completed, bad_scores = connection.execute("""
                SELECT count(*),count(*) FILTER(WHERE r.score<>(
                  SELECT count(*) FROM tasteduel.answers a WHERE a.game_id=r.game_id AND a.correct))
                FROM tasteduel.game_results r WHERE r.session_id=%s
            """, (owner,)).fetchone()
            frozen, bad_pairs = connection.execute("""
                SELECT count(*),count(*) FILTER(WHERE (
                  SELECT count(*) FROM tasteduel.challenge_rounds cr
                  JOIN tasteduel.delivered_rounds d ON d.id=cr.source_round_id
                  JOIN tasteduel.private_pairs p ON p.id=d.pair_id
                  WHERE cr.challenge_id=c.id AND cr.ordinal=d.ordinal
                    AND cr.left_entity_id=coalesce(d.left_entity_id,p.left_entity_id)
                    AND cr.right_entity_id=coalesce(d.right_entity_id,p.right_entity_id)
                    AND cr.winner_entity_id=p.winner_entity_id)<>5)
                FROM tasteduel.challenges c WHERE c.session_id=%s
            """, (owner,)).fetchone()
            if bad_scores or bad_pairs:
                raise RestoreBoundaryError("Restored game or frozen challenge invariant failed.")
            results += completed
            challenges += frozen
    if not results or not challenges:
        raise RestoreBoundaryError("Rehearsal requires an actual completed game and frozen challenge.")
    return {"owned_table_counts_match": True, "private_snapshot_digest_matches": True,
            "completed_results_verified": results, "frozen_challenges_verified": challenges,
            "managed_backup_restore_proven": False, "backup_payload_files_written": False}


def exercise_restored_replay(runtime_factory, target, owner):
    """Play a restored frozen challenge through the actual private API in memory.

    Creates only a fresh guest in the disposable target. Expected names/winners
    stay private; only factual booleans/counts are returned. No provider is enabled.
    """
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from tasteduel.api.main import create_app
    from tasteduel.config import Settings

    _target(target)
    with runtime_factory(target.name) as runtime:
        _identity(runtime, target.name, "tasteduel_runtime")
        marker = runtime.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()").fetchone()[0]
        if marker != target.marker:
            raise RestoreBoundaryError("Unexpected replay verification target.")
        runtime.execute("SELECT set_config('app.session_id',%s,true)", (str(UUID(str(owner))),))
        challenge = runtime.execute("SELECT id,share_slug FROM tasteduel.challenges WHERE session_id=%s AND revoked_at IS NULL AND expires_at>clock_timestamp() ORDER BY created_at LIMIT 1", (owner,)).fetchone()
        if not challenge:
            raise RestoreBoundaryError("An active restored challenge is required.")
        comparisons = runtime.execute("""SELECT l.name,l.entity_type,r.name,r.entity_type,w.name
            FROM tasteduel.challenge_rounds cr
            JOIN tasteduel.entities l ON l.id=cr.left_entity_id
            JOIN tasteduel.entities r ON r.id=cr.right_entity_id
            JOIN tasteduel.entities w ON w.id=cr.winner_entity_id
            WHERE cr.challenge_id=%s ORDER BY cr.ordinal""", (challenge[0],)).fetchall()
        if len(comparisons) != 5:
            raise RestoreBoundaryError("Restored challenge must contain five comparisons.")
    engine = create_engine("postgresql+psycopg://", creator=lambda: runtime_factory(target.name),
                           hide_parameters=True, pool_size=1, max_overflow=0)
    try:
        settings = Settings(database_mode="local", database_url=None, qloo_enabled=False,
                            generation_enabled=False, cookie_secure=True, allowed_origins=("https://restore-check.invalid",))
        with TestClient(create_app(settings, engine=engine), base_url="https://restore-check.invalid",
                        headers={"Origin": "https://restore-check.invalid"}, raise_server_exceptions=False) as guest:
            if guest.post("/v1/sessions", json={}).status_code != 201:
                raise RestoreBoundaryError("Restored replay guest creation failed.")
            response = guest.post(f"/v1/challenges/{challenge[1]}/plays", json={}, headers={"Idempotency-Key": "restore-play-" + secrets.token_hex(12)})
            if response.status_code != 201:
                raise RestoreBoundaryError("Restored replay creation failed.")
            game = response.json()
            score = 0
            for ordinal, (left, left_type, right, right_type, winner) in enumerate(comparisons, 1):
                current = game.get("current_round", {})
                choices = current.get("choices", [])
                if (current.get("ordinal") != ordinal or len(choices) != 2
                        or [(choice["entity"]["name"], choice["entity"]["type"]) for choice in choices] != [(left, left_type), (right, right_type)]):
                    raise RestoreBoundaryError("Restored replay comparison differs from the frozen source.")
                answered = guest.post(f"/v1/games/{game['game_id']}/answer", json={
                    "round_id": current["round_id"], "choice_id": choices[0]["id"], "expected_revision": current["revision"],
                }, headers={"Idempotency-Key": "restore-answer-" + secrets.token_hex(12)})
                if answered.status_code != 200:
                    raise RestoreBoundaryError("Restored answer acceptance failed.")
                reveal = answered.json()
                actual = next(choice["entity"]["name"] for choice in reveal["choices"] if choice["id"] == reveal["winning_choice_id"])
                if actual != winner:
                    raise RestoreBoundaryError("Restored replay changed a frozen winner.")
                score += int(reveal["correct"])
                advanced = guest.post(f"/v1/games/{game['game_id']}/advance", json={
                    "answered_round_id": reveal["round_id"], "expected_revision": reveal["revision"],
                }, headers={"Idempotency-Key": "restore-next-" + secrets.token_hex(12)})
                if advanced.status_code != 200:
                    raise RestoreBoundaryError("Restored replay advancement failed.")
                game = advanced.json()
            if game["phase"] != "completed" or game["score"] != score:
                raise RestoreBoundaryError("Restored replay final score failed.")
        return {"restored_five_round_api_replay": True, "stored_comparisons_and_winners_preserved": True,
                "independent_restored_guest_score_verified": True, "provider_calls": 0}
    finally:
        engine.dispose()


def drop_target(admin_factory, target):
    """Drop only the exact created target with matching marker/owner and no clients."""
    _target(target)
    with admin_factory("tasteduel") as admin:
        _identity(admin, "tasteduel", "accesslife")
        identity = admin.execute("SELECT pg_get_userbyid(datdba),shobj_description(oid,'pg_database') FROM pg_database WHERE datname=%s", (target.name,)).fetchone()
        if identity is None:
            return {"exact_disposable_database_removed": False, "target_already_absent": True}
        if identity != ("accesslife", target.marker):
            raise RestoreBoundaryError("Refusing deletion of an unverified disposable database.")
        active = admin.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=%s", (target.name,)).fetchone()[0]
        admin.rollback()
        if active:
            raise RestoreBoundaryError("Restore clients must close before disposable cleanup.")
        admin.autocommit = True
        admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(target.name)))
    return {"exact_disposable_database_removed": True}
