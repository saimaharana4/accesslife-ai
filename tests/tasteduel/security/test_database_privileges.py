"""Independent checks of the real local runtime role, not an in-memory database.

The session GUC is trusted application context, not a database authentication
mechanism. API tests separately prove that an HTTP caller cannot choose it.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError


def test_runtime_role_cannot_bypass_policies_or_administer_database(db_engine):
    with db_engine.connect() as connection:
        role = connection.execute(
            text(
                "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole "
                "FROM pg_roles WHERE rolname = current_user"
            )
        ).one()
    assert tuple(role) == (False, False, False, False)


def test_runtime_cannot_create_tables_in_application_schema(db_engine):
    with db_engine.connect() as connection:
        schema = connection.execute(text("SELECT current_schema()")).scalar_one()
        assert (
            connection.execute(
                text("SELECT has_schema_privilege(current_user, :schema, 'CREATE')"),
                {"schema": schema},
            ).scalar_one()
            is False
        )

    # Exercise the server's permission boundary in addition to its catalog flags.
    # An unexpected success is rolled back, so this check never leaves a table.
    with db_engine.connect() as connection:
        transaction = connection.begin()
        try:
            with pytest.raises(DBAPIError) as failure:
                connection.execute(text("CREATE TABLE secrecy_test_ddl_probe (id integer)"))
            assert failure.value.orig.sqlstate == "42501"
        finally:
            transaction.rollback()


def test_runtime_cannot_assume_the_migration_role(db_engine, db_owner_engine):
    with db_owner_engine.connect() as connection:
        migration_role = connection.execute(text("SELECT current_user")).scalar_one()
    with db_engine.connect() as connection:
        runtime_role = connection.execute(text("SELECT current_user")).scalar_one()
        connection.rollback()
        assert runtime_role != migration_role
        quoted_role = connection.dialect.identifier_preparer.quote(migration_role)
        transaction = connection.begin()
        try:
            with pytest.raises(DBAPIError) as failure:
                connection.execute(text(f"SET LOCAL ROLE {quoted_role}"))
            assert failure.value.orig.sqlstate == "42501"
        finally:
            transaction.rollback()
