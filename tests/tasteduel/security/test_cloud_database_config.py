"""Cloud guard and secret-resolution contracts; synthetic URLs, no ADC/network."""

import pytest
from pydantic import ValidationError

from tasteduel.adapters.database_secrets import DatabaseConfigurationError, resolve_database_url
from tasteduel.config import CLOUD_SQL_CONNECTION, SECRET_PREFIX, Settings, validate_database_url, validate_local_url
from tasteduel.persistence import db


@pytest.fixture(autouse=True)
def isolated_cloud_configuration(monkeypatch):
    monkeypatch.delenv("TASTEDUEL_DATABASE_URL", raising=False)
    monkeypatch.delenv("TASTEDUEL_MIGRATION_DATABASE_URL", raising=False)


def cloud_url(*, user="tasteduel_runtime", database="tasteduel", query=None):
    return f"postgresql+psycopg://{user}:SYNTHETIC_PRIVATE_PASSWORD@/{database}?" + (
        query if query is not None else "host=/cloudsql/" + CLOUD_SQL_CONNECTION
    )


def cloud_settings(**overrides):
    values = dict(database_mode="cloud_sql", database_secret_version=SECRET_PREFIX + "tasteduel-runtime-database-url/versions/1",
                  migration_database_secret_version=SECRET_PREFIX + "tasteduel-migrate-database-url/versions/1",
                  allowed_origins=("https://reviewed-candidate.example.invalid",),
                  vertex_requests_per_day=50, vertex_tokens_per_day=500_000)
    return Settings(**{**values, **overrides})


@pytest.mark.parametrize("user,database,query", [
    ("accesslife", "tasteduel", None), ("tasteduel_migrator", "tasteduel", None),
    ("tasteduel_runtime", "accesslife", None), ("tasteduel_runtime", "postgres", None),
    ("tasteduel_runtime", "tasteduel", "host=/cloudsql/other-instance"),
    ("tasteduel_runtime", "tasteduel", "host=/cloudsql/" + CLOUD_SQL_CONNECTION + "&options=-cbypassrls=on"),
    ("tasteduel_runtime", "tasteduel", "host=127.0.0.1"),
    ("tasteduel_runtime", "tasteduel", "host=/cloudsql/" + CLOUD_SQL_CONNECTION + "&host=external.invalid"),
])
def test_cloud_guard_rejects_wrong_scope_and_connection_overrides(user, database, query):
    with pytest.raises(ValueError) as failure:
        validate_database_url(cloud_url(user=user, database=database, query=query), mode="cloud_sql")
    assert "SYNTHETIC_PRIVATE" not in str(failure.value)


def test_cloud_and_local_modes_do_not_implicitly_accept_each_other():
    with pytest.raises(ValueError):
        validate_local_url(cloud_url())
    local = "postgresql+psycopg://tasteduel_runtime:synthetic@127.0.0.1:55435/tasteduel_prompt5"
    with pytest.raises(ValueError):
        validate_database_url(local, mode="cloud_sql")
    with pytest.raises(ValueError):
        validate_local_url(local + "?host=external.invalid")


def test_secret_references_are_role_specific_numeric_and_same_project():
    calls = []
    settings = cloud_settings()
    assert resolve_database_url(settings, reader=lambda ref: calls.append(ref) or cloud_url()) == cloud_url()
    assert calls == [SECRET_PREFIX + "tasteduel-runtime-database-url/versions/1"]
    assert resolve_database_url(settings, migration=True, reader=lambda ref: cloud_url(user="tasteduel_migrator"))
    for reference in [SECRET_PREFIX + "accesslife-database-url/versions/1", SECRET_PREFIX + "tasteduel-runtime-database-url/versions/latest",
                      "projects/another-project/secrets/tasteduel-runtime-database-url/versions/1"]:
        with pytest.raises(ValidationError):
            Settings(database_secret_version=reference)


def test_missing_secret_and_auth_failures_are_sanitized_without_fallback(monkeypatch):
    monkeypatch.delenv("TASTEDUEL_MIGRATION_DATABASE_URL", raising=False)
    calls = []

    def fail(reference):
        calls.append(reference)
        raise RuntimeError("SYNTHETIC_PRIVATE_SECRET_AND_PROVIDER_DIAGNOSTIC")

    with pytest.raises(DatabaseConfigurationError) as failure:
        resolve_database_url(cloud_settings(), reader=fail)
    assert "SYNTHETIC_PRIVATE" not in str(failure.value)
    assert len(calls) == 1


def test_raw_cloud_url_cannot_override_a_pinned_reference():
    with pytest.raises(DatabaseConfigurationError):
        resolve_database_url(cloud_settings(database_url=cloud_url()), reader=lambda _: pytest.fail("Unexpected secret call"))


@pytest.mark.parametrize("field,value", [("cookie_secure", False), ("vertex_project", "other-project"),
                                         ("qloo_enabled", True), ("allowed_origins", ("http://localhost:3000",))])
def test_cloud_release_guards_fail_before_reading_secrets(field, value):
    with pytest.raises(DatabaseConfigurationError):
        resolve_database_url(cloud_settings(**{field: value}), reader=lambda _: pytest.fail("Unexpected secret call"))


def test_cloud_engine_has_small_pool_no_overflow_and_fixed_search_path(monkeypatch):
    captured = {}

    def engine(url, **kwargs):
        captured.update(kwargs)
        return "synthetic-engine"

    monkeypatch.setattr(db, "create_engine", engine)
    assert db.database_engine(cloud_url(), mode="cloud_sql") == "synthetic-engine"
    assert captured["pool_size"] == 2 and captured["max_overflow"] == 0
    assert captured["hide_parameters"] is True
    assert captured["connect_args"]["options"] == "-csearch_path=tasteduel,pg_catalog"
