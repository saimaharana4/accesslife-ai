"""Guarded empty-database foundation bootstrap, independent of app migrations.

Library entry points accept already-authenticated psycopg connections. They never
resolve/export credentials, read old app rows, or implement a command-line apply.
An authorized caller must supply the reviewed connection and handle failures
without printing DSNs or server diagnostics. No SQL is executed on import.
"""

from uuid import uuid4

DATABASE = "tasteduel"
RUNTIME = "tasteduel_runtime"
MIGRATOR = "tasteduel_migrator"
ACTORS = (RUNTIME, MIGRATOR)
ALLOWED_INITIAL_MEMBERSHIPS = frozenset({"cloudsqlsuperuser"})


class FoundationBoundaryError(RuntimeError):
    """Public-safe failure: never embeds SQL, credentials or server messages."""


def _identity(connection, expected_user=None):
    database, user = connection.execute("SELECT current_database(), current_user").fetchone()
    if database != DATABASE or (expected_user is not None and user != expected_user):
        raise FoundationBoundaryError("Unexpected foundation database or principal.")
    return user


def _role_rows(connection):
    return connection.execute(
        "SELECT rolname,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls,rolcanlogin "
        "FROM pg_roles WHERE rolname IN (%s,%s) ORDER BY rolname", ACTORS,
    ).fetchall()


def _memberships(connection):
    return connection.execute(
        "SELECT member_role.rolname,parent_role.rolname FROM pg_auth_members m "
        "JOIN pg_roles member_role ON member_role.oid=m.member "
        "JOIN pg_roles parent_role ON parent_role.oid=m.roleid "
        "WHERE member_role.rolname IN (%s,%s)", ACTORS,
    ).fetchall()


def bootstrap(connection):
    """Commit only empty tasteduel role/schema preparation after invariant checks.

    Uses a single transaction. Unknown memberships, app tables, existing foreign
    schemas/owners, missing roles or insufficient administrative authority abort
    the transaction. Never modifies old database grants or role ownership.
    """
    # An outer transaction would turn this into a savepoint and make a reported
    # success non-durable. Require a fresh/committed administrative connection.
    if int(connection.info.transaction_status) != 0:
        raise FoundationBoundaryError("Foundation requires an idle administrative transaction.")
    try:
        with connection.transaction():
            admin = _identity(connection)
            if admin in ACTORS:
                raise FoundationBoundaryError("Administrative foundation principal required.")
            connection.execute("SELECT pg_advisory_xact_lock(836121710)")
            rows = _role_rows(connection)
            if {row[0] for row in rows} != set(ACTORS):
                raise FoundationBoundaryError("Foundation requires both pre-created SQL principals.")
            if any(row[1] or row[4] or row[5] for row in rows):
                raise FoundationBoundaryError("Unexpected privileged SQL attribute; administrative review required.")
            memberships = _memberships(connection)
            if any(parent not in ALLOWED_INITIAL_MEMBERSHIPS for _, parent in memberships):
                raise FoundationBoundaryError("Unexpected inherited SQL membership; no changes committed.")
            schemas = connection.execute(
                "SELECT nspname,pg_get_userbyid(nspowner) FROM pg_namespace "
                "WHERE nspname NOT LIKE 'pg_%' AND nspname <> 'information_schema'"
            ).fetchall()
            if any(name not in {"public", "tasteduel"} or (name == "tasteduel" and owner != MIGRATOR) for name, owner in schemas):
                raise FoundationBoundaryError("Unexpected foundation schema or ownership.")
            count = connection.execute(
                "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema' "
                "AND c.relkind IN ('r','p','v','m','S','f')"
            ).fetchone()[0]
            if count:
                raise FoundationBoundaryError("Foundation bootstrap is restricted to an empty database.")
            for actor, parent in memberships:
                # Both identifiers are exact constants verified above; no input SQL.
                connection.execute(f'REVOKE "{parent}" FROM "{actor}"')
            for actor in ACTORS:
                # Cloud SQL administrators are not PostgreSQL superusers. Even
                # requesting NOSUPERUSER/NOREPLICATION/NOBYPASSRLS can require
                # powers they do not have. Assert these already-false attributes
                # before/after, and alter only ordinary role-admin attributes.
                connection.execute(f'ALTER ROLE "{actor}" NOCREATEDB NOCREATEROLE NOINHERIT')
            connection.execute('REVOKE ALL PRIVILEGES ON DATABASE "tasteduel" FROM PUBLIC')
            connection.execute('REVOKE ALL PRIVILEGES ON DATABASE "tasteduel" FROM "tasteduel_runtime", "tasteduel_migrator"')
            connection.execute('GRANT CONNECT ON DATABASE "tasteduel" TO "tasteduel_runtime", "tasteduel_migrator"')
            connection.execute('REVOKE ALL ON SCHEMA public FROM PUBLIC, "tasteduel_runtime", "tasteduel_migrator"')
            connection.execute('CREATE SCHEMA IF NOT EXISTS tasteduel AUTHORIZATION "tasteduel_migrator"')
            connection.execute('REVOKE ALL ON SCHEMA tasteduel FROM PUBLIC, "tasteduel_runtime"')
            connection.execute('GRANT USAGE ON SCHEMA tasteduel TO "tasteduel_runtime"')
            if _memberships(connection) or any(any(row[1:6]) or not row[6] for row in _role_rows(connection)):
                raise FoundationBoundaryError("SQL role restriction verification failed.")
        return {"database": DATABASE, "schema_prepared": True, "role_flags_verified": True,
                "direct_memberships_remaining": 0, "application_migrations_run": False}
    except FoundationBoundaryError:
        raise
    except Exception:
        raise FoundationBoundaryError("Foundation SQL preparation failed; transaction rolled back.") from None


def _staged_preflight(connection, *, administrator=False):
    user = _identity(connection, None if administrator else MIGRATOR)
    if administrator and user in ACTORS:
        raise FoundationBoundaryError("Administrative foundation principal required.")
    rows = _role_rows(connection)
    if {row[0] for row in rows} != set(ACTORS) or any(row[1] or row[4] or row[5] for row in rows):
        raise FoundationBoundaryError("Unexpected foundation role boundary.")
    if any(parent not in ALLOWED_INITIAL_MEMBERSHIPS for _, parent in _memberships(connection)):
        raise FoundationBoundaryError("Unexpected foundation role membership.")
    schemas = connection.execute(
        "SELECT nspname,pg_get_userbyid(nspowner) FROM pg_namespace "
        "WHERE nspname NOT LIKE 'pg_%' AND nspname <> 'information_schema'"
    ).fetchall()
    if any(name not in {"public", "tasteduel"} or (name == "tasteduel" and owner != MIGRATOR) for name, owner in schemas):
        raise FoundationBoundaryError("Unexpected foundation schema or ownership.")
    count = connection.execute(
        "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema' "
        "AND c.relkind IN ('r','p','v','m','S','f')"
    ).fetchone()[0]
    if count:
        raise FoundationBoundaryError("Foundation bootstrap is restricted to an empty database.")


def bootstrap_staged(admin_connection, migrator_connection):
    """Prepare only the new database without granting migrator membership to admin.

    Three committed stages are necessary when the Cloud SQL admin cannot SET
    ROLE to the migrator: role restriction + temporary new-DB CREATE; independent
    migrator-owned schema creation; administrative removal of temporary CREATE.
    Failure is explicit, with a best-effort narrow CREATE revoke after preparation.
    Existing entry points retain their original single-transaction behavior.
    """
    if any(int(connection.info.transaction_status) != 0 for connection in (admin_connection, migrator_connection)):
        raise FoundationBoundaryError("Staged foundation requires idle independent connections.")
    prepared = False
    stage = "identity"
    try:
        with migrator_connection.transaction(force_rollback=True):
            _identity(migrator_connection, MIGRATOR)
        stage = "role_preparation"
        with admin_connection.transaction():
            _staged_preflight(admin_connection, administrator=True)
            admin_connection.execute("SELECT pg_advisory_xact_lock(836121710)")
            for actor, parent in _memberships(admin_connection):
                admin_connection.execute(f'REVOKE "{parent}" FROM "{actor}"')
            for actor in ACTORS:
                admin_connection.execute(f'ALTER ROLE "{actor}" NOCREATEDB NOCREATEROLE NOINHERIT')
            admin_connection.execute('REVOKE ALL PRIVILEGES ON DATABASE "tasteduel" FROM PUBLIC')
            admin_connection.execute('REVOKE ALL PRIVILEGES ON DATABASE "tasteduel" FROM "tasteduel_runtime", "tasteduel_migrator"')
            admin_connection.execute('GRANT CONNECT ON DATABASE "tasteduel" TO "tasteduel_runtime", "tasteduel_migrator"')
            admin_connection.execute('REVOKE ALL ON SCHEMA public FROM PUBLIC, "tasteduel_runtime", "tasteduel_migrator"')
            admin_connection.execute('GRANT CREATE ON DATABASE "tasteduel" TO "tasteduel_migrator"')
            if _memberships(admin_connection) or any(any(row[1:6]) or not row[6] for row in _role_rows(admin_connection)):
                raise FoundationBoundaryError("SQL role restriction verification failed.")
        prepared = True
        stage = "schema_preparation"
        with migrator_connection.transaction():
            _staged_preflight(migrator_connection)
            if _memberships(migrator_connection) or any(any(row[1:6]) for row in _role_rows(migrator_connection)):
                raise FoundationBoundaryError("Migration login is not restricted.")
            migrator_connection.execute('CREATE SCHEMA IF NOT EXISTS tasteduel AUTHORIZATION "tasteduel_migrator"')
            migrator_connection.execute('REVOKE ALL ON SCHEMA tasteduel FROM PUBLIC, "tasteduel_runtime"')
            migrator_connection.execute('GRANT USAGE ON SCHEMA tasteduel TO "tasteduel_runtime"')
        stage = "temporary_grant_removal"
        with admin_connection.transaction():
            _staged_preflight(admin_connection, administrator=True)
            admin_connection.execute('REVOKE CREATE ON DATABASE "tasteduel" FROM "tasteduel_migrator"')
            if _memberships(admin_connection) or any(any(row[1:6]) for row in _role_rows(admin_connection)):
                raise FoundationBoundaryError("Final foundation role verification failed.")
            privileges = admin_connection.execute(
                "SELECT has_database_privilege('tasteduel_runtime','tasteduel','CREATE'), "
                "has_database_privilege('tasteduel_runtime','tasteduel','TEMP'), "
                "has_database_privilege('tasteduel_migrator','tasteduel','CREATE'), "
                "has_database_privilege('tasteduel_migrator','tasteduel','TEMP'), "
                "has_schema_privilege('tasteduel_runtime','tasteduel','USAGE'), "
                "has_schema_privilege('tasteduel_runtime','tasteduel','CREATE')"
            ).fetchone()
            if tuple(privileges) != (False, False, False, False, True, False):
                raise FoundationBoundaryError("Final foundation database grants failed verification.")
        return {"database": DATABASE, "schema_prepared": True, "role_flags_verified": True,
                "direct_memberships_remaining": 0, "temporary_database_create_revoked": True,
                "committed_stages": 3, "application_migrations_run": False}
    except Exception:
        cleanup_completed = False
        if prepared:
            try:
                with admin_connection.transaction():
                    if _identity(admin_connection) in ACTORS:
                        raise FoundationBoundaryError("Unexpected cleanup principal.")
                    admin_connection.execute('REVOKE CREATE ON DATABASE "tasteduel" FROM "tasteduel_migrator"')
                    cleanup_completed = admin_connection.execute(
                        "SELECT has_database_privilege('tasteduel_migrator','tasteduel','CREATE')"
                    ).fetchone()[0] is False
            except Exception:
                pass
        error = FoundationBoundaryError("Staged foundation failed at " + stage + "; inspect only sanitized execution status.")
        error.preparation_committed = prepared
        error.temporary_create_cleanup_completed = cleanup_completed
        raise error from None


def verify_runtime(connection):
    """Verify a real runtime login with no legacy row reads or persistent writes."""
    try:
        with connection.transaction(force_rollback=True):
            _identity(connection, RUNTIME)
            rows = _role_rows(connection)
            runtime = next(row for row in rows if row[0] == RUNTIME)
            if any(runtime[1:6]) or _memberships(connection):
                raise FoundationBoundaryError("Unexpected runtime role powers or memberships.")
            checks = connection.execute(
                "SELECT has_database_privilege(current_user,'tasteduel','CONNECT'), "
                "has_database_privilege(current_user,'tasteduel','CREATE'), "
                "has_database_privilege(current_user,'tasteduel','TEMP'), "
                "has_schema_privilege(current_user,'tasteduel','USAGE'), "
                "has_schema_privilege(current_user,'tasteduel','CREATE'), "
                "has_schema_privilege(current_user,'public','CREATE')"
            ).fetchone()
            if tuple(checks) != (True, False, False, True, False, False):
                raise FoundationBoundaryError("Runtime database/schema privilege verification failed.")
        return {"runtime_login_verified": True, "runtime_ddl_denied": True,
                "application_table_rls_verified": False, "old_database_access_verified": False}
    except FoundationBoundaryError:
        raise
    except Exception:
        raise FoundationBoundaryError("Runtime privilege verification failed.") from None


def verify_migrator(connection):
    """Verify an independent migrator login and actual DDL; always roll it back."""
    try:
        with connection.transaction(force_rollback=True):
            _identity(connection, MIGRATOR)
            row = next(row for row in _role_rows(connection) if row[0] == MIGRATOR)
            if any(row[1:6]) or _memberships(connection):
                raise FoundationBoundaryError("Unexpected migration role powers or memberships.")
            name = "foundation_probe_" + uuid4().hex
            connection.execute(f'CREATE TABLE tasteduel."{name}" (id integer)')
        return {"migration_login_verified": True, "migration_ddl_rolled_back": True,
                "application_migrations_run": False}
    except FoundationBoundaryError:
        raise
    except Exception:
        raise FoundationBoundaryError("Migration privilege verification failed.") from None
