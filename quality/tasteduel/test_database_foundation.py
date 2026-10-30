"""Synthetic executor boundary tests; independent real logins remain a live gate."""

from contextlib import contextmanager
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("database_foundation", ROOT / "scripts/tasteduel_database_foundation.py")
foundation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(foundation)


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0]

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, *, database="tasteduel", user="postgres", parent="cloudsqlsuperuser", tables=0):
        self.info = SimpleNamespace(transaction_status=0)
        self.database, self.user, self.parent, self.tables = database, user, parent, tables
        self.commands = []
        self.restricted = False
        self.rolled_back = False
        self.committed = False
        self.failure = None

    @contextmanager
    def transaction(self, *, force_rollback=False):
        try:
            yield
        except Exception:
            self.rolled_back = True
            raise
        else:
            self.rolled_back = force_rollback
            self.committed = not force_rollback

    def execute(self, sql, parameters=None):
        self.commands.append((sql, parameters))
        if self.failure and self.failure in sql:
            raise RuntimeError("SYNTHETIC_SECRET_DATABASE_DIAGNOSTIC")
        if "current_database()" in sql:
            return Cursor([(self.database, self.user)])
        if "FROM pg_roles WHERE" in sql:
            return Cursor([(actor, False, not self.restricted, not self.restricted, False, False, True) for actor in foundation.ACTORS])
        if "FROM pg_auth_members" in sql:
            return Cursor([(actor, self.parent) for actor in foundation.ACTORS] if self.parent else [])
        if sql.startswith("SELECT nspname"):
            return Cursor([("public", "pg_database_owner")])
        if "SELECT count(*) FROM pg_class" in sql:
            return Cursor([(self.tables,)])
        if sql.startswith("REVOKE \"cloudsqlsuperuser\""):
            self.parent = None
        if sql.startswith("ALTER ROLE"):
            self.restricted = True
        if sql.startswith("SELECT has_database_privilege"):
            return Cursor([(True, False, False, True, False, False)])
        return Cursor([(None,)])


@pytest.mark.parametrize("database,user", [("accesslife", "postgres"), ("postgres", "postgres"), ("tasteduel", "tasteduel_runtime"), ("tasteduel", "tasteduel_migrator")])
def test_wrong_database_or_admin_fails_before_any_write(database, user):
    connection = Connection(database=database, user=user)
    with pytest.raises(foundation.FoundationBoundaryError):
        foundation.bootstrap(connection)
    assert all(sql.startswith("SELECT") for sql, _ in connection.commands)
    assert connection.rolled_back and not connection.committed


@pytest.mark.parametrize("parent,tables", [("unexpected_admin_group", 0), ("cloudsqlsuperuser", 1)])
def test_unknown_membership_or_nonempty_database_fails_closed(parent, tables):
    connection = Connection(parent=parent, tables=tables)
    with pytest.raises(foundation.FoundationBoundaryError):
        foundation.bootstrap(connection)
    assert all(sql.startswith("SELECT") for sql, _ in connection.commands)
    assert connection.rolled_back


def test_bootstrap_removes_initial_elevation_and_only_changes_new_scope():
    connection = Connection()
    result = foundation.bootstrap(connection)
    statements = [sql for sql, _ in connection.commands]
    assert connection.committed
    assert result["application_migrations_run"] is False
    assert result["direct_memberships_remaining"] == 0
    writes = [sql for sql in statements if not sql.startswith("SELECT")]
    assert len([sql for sql in writes if sql.startswith("ALTER ROLE")]) == 2
    assert not any("accesslife" in sql or "PASSWORD" in sql or "GRANT ALL" in sql for sql in writes)
    assert all("NOCREATEDB NOCREATEROLE NOINHERIT" in sql for sql in writes if sql.startswith("ALTER ROLE"))
    assert not any("NOSUPERUSER" in sql or "NOBYPASSRLS" in sql or "NOREPLICATION" in sql for sql in writes)


@pytest.mark.parametrize("flag_index", [1, 4, 5])
def test_privileged_attributes_are_not_silently_repaired(monkeypatch, flag_index):
    connection = Connection()
    row = [foundation.RUNTIME, False, True, True, False, False, True]
    row[flag_index] = True
    monkeypatch.setattr(foundation, "_role_rows", lambda _: [tuple(row), (foundation.MIGRATOR, False, True, True, False, False, True)])
    with pytest.raises(foundation.FoundationBoundaryError):
        foundation.bootstrap(connection)
    assert all(sql.startswith("SELECT") for sql, _ in connection.commands)


def test_server_error_is_sanitized_and_transaction_not_committed():
    connection = Connection()
    connection.failure = "CREATE SCHEMA"
    with pytest.raises(foundation.FoundationBoundaryError) as error:
        foundation.bootstrap(connection)
    assert "SYNTHETIC_SECRET" not in str(error.value)
    assert error.value.__suppress_context__
    assert connection.rolled_back and not connection.committed


def test_existing_transaction_cannot_masquerade_as_committed_bootstrap():
    connection = Connection()
    connection.info.transaction_status = 2
    with pytest.raises(foundation.FoundationBoundaryError):
        foundation.bootstrap(connection)
    assert connection.commands == []


def test_runtime_verification_uses_real_principal_contract_not_admin_set_role():
    connection = Connection(user="postgres", parent=None)
    connection.restricted = True
    with pytest.raises(foundation.FoundationBoundaryError):
        foundation.verify_runtime(connection)
    assert not any("SET ROLE" in sql for sql, _ in connection.commands)
    runtime = Connection(user="tasteduel_runtime", parent=None)
    runtime.restricted = True
    result = foundation.verify_runtime(runtime)
    assert runtime.rolled_back and not runtime.committed
    assert result["old_database_access_verified"] is False
    assert result["application_table_rls_verified"] is False


def test_migration_ddl_probe_is_rolled_back_and_not_application_migration():
    connection = Connection(user="tasteduel_migrator", parent=None)
    connection.restricted = True
    result = foundation.verify_migrator(connection)
    assert connection.rolled_back and not connection.committed
    assert result["application_migrations_run"] is False
    assert any(sql.startswith('CREATE TABLE tasteduel."foundation_probe_') for sql, _ in connection.commands)


def staged_pair():
    admin, migrator = Connection(), Connection(user=foundation.MIGRATOR)
    state = {"schema": False}
    for connection, other in [(admin, migrator), (migrator, admin)]:
        execute = connection.execute

        def staged_execute(sql, parameters=None, *, execute=execute, other=other):
            if sql == "SELECT has_database_privilege('tasteduel_migrator','tasteduel','CREATE')":
                execute(sql, parameters)
                return Cursor([(False,)])
            if sql.startswith("SELECT has_database_privilege('tasteduel_runtime'"):
                execute(sql, parameters)
                return Cursor([(False, False, False, False, True, False)])
            if sql.startswith("SELECT nspname") and state["schema"]:
                execute(sql, parameters)
                return Cursor([("public", "pg_database_owner"), ("tasteduel", foundation.MIGRATOR)])
            result = execute(sql, parameters)
            if sql.startswith("ALTER ROLE"):
                other.restricted = True
            if sql.startswith('REVOKE "cloudsqlsuperuser"'):
                other.parent = None
            if sql.startswith("CREATE SCHEMA"):
                state["schema"] = True
            return result

        connection.execute = staged_execute
    return admin, migrator


def test_staged_schema_is_created_only_by_its_own_login_without_admin_membership():
    admin, migrator = staged_pair()
    result = foundation.bootstrap_staged(admin, migrator)
    assert result["committed_stages"] == 3
    assert result["temporary_database_create_revoked"]
    admin_writes = [sql for sql, _ in admin.commands if not sql.startswith("SELECT")]
    assert not any("CREATE SCHEMA" in sql or "SET ROLE" in sql for sql in admin_writes)
    assert 'GRANT CREATE ON DATABASE "tasteduel" TO "tasteduel_migrator"' in admin_writes
    assert 'REVOKE CREATE ON DATABASE "tasteduel" FROM "tasteduel_migrator"' in admin_writes
    assert any(sql.startswith("CREATE SCHEMA") for sql, _ in migrator.commands)
    assert not any("accesslife" in sql or "PASSWORD" in sql for sql in admin_writes)


def test_staged_schema_failure_cleans_only_temporary_create_and_reports_partial_commit():
    admin, migrator = staged_pair()
    migrator.failure = "CREATE SCHEMA"
    with pytest.raises(foundation.FoundationBoundaryError) as error:
        foundation.bootstrap_staged(admin, migrator)
    assert error.value.preparation_committed
    assert error.value.temporary_create_cleanup_completed
    assert "schema_preparation" in str(error.value)
    assert "SYNTHETIC_SECRET" not in str(error.value)
    assert admin.commands[-2][0] == 'REVOKE CREATE ON DATABASE "tasteduel" FROM "tasteduel_migrator"'


def test_staged_wrong_migrator_principal_fails_before_any_administrative_write():
    admin, migrator = staged_pair()
    migrator.user = "postgres"
    with pytest.raises(foundation.FoundationBoundaryError) as error:
        foundation.bootstrap_staged(admin, migrator)
    assert not error.value.preparation_committed
    assert admin.commands == []


def test_staged_retry_accepts_only_prepared_empty_owned_schema():
    admin, migrator = staged_pair()
    foundation.bootstrap_staged(admin, migrator)
    result = foundation.bootstrap_staged(admin, migrator)
    assert result["temporary_database_create_revoked"]
