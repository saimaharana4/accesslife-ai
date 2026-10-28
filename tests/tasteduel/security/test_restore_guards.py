"""Logical rehearsal destructive-boundary guards; no cloud or credential access."""

from datetime import UTC, datetime, timedelta
import hashlib
from uuid import uuid4

import pytest

from scripts import tasteduel_restore as restore


class NoDatabaseAccess:
    def execute(self, *args, **kwargs):
        pytest.fail("Boundary rejection must precede database access")


@pytest.mark.parametrize("name", ["tasteduel", "accesslife", "postgres", "tasteduel_restore_other", "tasteduel_restore_" + "a" * 16 + ";DROP DATABASE accesslife"])
def test_live_and_unverified_database_names_can_never_be_restore_or_delete_targets(name):
    target = restore.RestoreTarget(name, "tasteduel-disposable:" + "a" * 32)
    with pytest.raises(restore.RestoreBoundaryError):
        restore.restore_sessions(NoDatabaseAccess(), target, None)
    with pytest.raises(restore.RestoreBoundaryError):
        restore.drop_target(lambda _: pytest.fail("Unexpected factory invocation"), target)


def memory_backup(*, expired=False, corrupt=False, relation="sessions"):
    owner = uuid4()
    payload = b"SYNTHETIC_PRIVATE_BACKUP_NOT_A_PROVIDER_RESPONSE"
    digest = hashlib.sha256(relation.encode() + owner.bytes + payload).hexdigest()
    return restore.MemoryBackup((owner,), "td0010", datetime.now(UTC) + timedelta(seconds=-10 if expired else 60),
                                [(relation, owner, payload)], {(relation, owner): 1}, len(payload),
                                "0" * 64 if corrupt else digest)


def test_expired_evidence_is_rejected_before_restore_mutations():
    with pytest.raises(restore.RestoreBoundaryError, match="expired"):
        restore.restore_sessions(NoDatabaseAccess(), restore.RestoreTarget.fresh(), memory_backup(expired=True))


def test_corrupt_or_arbitrary_relations_are_rejected_before_restore_mutations():
    for backup in [memory_backup(corrupt=True), memory_backup(relation="public.sessions; DROP SCHEMA tasteduel CASCADE")]:
        with pytest.raises(restore.RestoreBoundaryError):
            restore.restore_sessions(NoDatabaseAccess(), restore.RestoreTarget.fresh(), backup)


def test_memory_backup_repr_never_displays_private_bytes_or_owner_ids():
    backup = memory_backup()
    assert "SYNTHETIC_PRIVATE" not in repr(backup)
    assert str(backup.owners[0]) not in repr(backup)


def test_session_snapshot_requires_a_small_explicit_distinct_owner_set():
    owner = uuid4()
    for owners in [[], [owner, owner], [uuid4(), uuid4(), uuid4()]]:
        with pytest.raises(restore.RestoreBoundaryError):
            restore.export_sessions(NoDatabaseAccess(), owners)


def test_offline_owned_schema_export_needs_no_secret_and_preserves_dynamic_sql(monkeypatch):
    from tasteduel.adapters import database_secrets

    monkeypatch.setattr(database_secrets, "resolve_database_url", lambda *a, **kw: pytest.fail("Offline DDL must not resolve secrets"))
    schema = restore.render_schema_sql()
    assert "td0010" in schema
    assert "FORCE ROW LEVEL SECURITY" in schema
    assert "TO tasteduel_runtime" in schema
    assert "%%I" not in schema  # psycopg placeholder escaping is not raw SQL DDL.
    assert "CREATE DATABASE" not in schema and "DROP DATABASE" not in schema
