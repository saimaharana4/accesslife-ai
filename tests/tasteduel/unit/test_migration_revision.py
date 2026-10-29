"""Migration success must reflect the database, not only subprocess exit code."""

from types import SimpleNamespace

import pytest

from tasteduel.operations import OperationBlocked, verified_schema_revision


@pytest.mark.parametrize("revision", ["td0011", "td0013", None])
def test_incomplete_schema_is_not_reported_as_migrated(revision):
    db = SimpleNamespace(execute=lambda statement: SimpleNamespace(scalar_one=lambda: revision))
    with pytest.raises(OperationBlocked, match="MIGRATION_REVISION_VERIFICATION_FAILED"):
        verified_schema_revision(db)


def test_migration_returns_verified_database_head():
    statements = []
    def execute(statement):
        statements.append(str(statement))
        return SimpleNamespace(scalar_one=lambda: "td0014")
    assert verified_schema_revision(SimpleNamespace(execute=execute)) == "td0014"
    assert statements == ["SELECT version_num FROM tasteduel.tasteduel_alembic_version"]
