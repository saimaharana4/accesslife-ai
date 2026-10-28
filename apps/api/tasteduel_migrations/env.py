"""Taste Duel-only local/explicit Cloud SQL lineage; no legacy DATABASE_URL."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from tasteduel.adapters.database_secrets import resolve_database_url
from tasteduel.config import Settings
from tasteduel.persistence.models import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

settings = Settings()
# Trusted offline schema rendering has no network/credential requirement and
# cannot select an execution database. Only an in-process Alembic Config flag
# enables it, never an environment variable or HTTP request.
url = ("postgresql+psycopg://" if context.is_offline_mode() and config.attributes.get("tasteduel_schema_export") is True
       else resolve_database_url(settings, migration=True))


def run_migrations():
    if context.is_offline_mode():
        context.configure(
            url=url,
            target_metadata=Base.metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
            version_table="tasteduel_alembic_version",
            version_table_schema="tasteduel",
        )
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = create_engine(url, poolclass=pool.NullPool, hide_parameters=True,
                           connect_args={"connect_timeout": 5, "application_name": "tasteduel-migrate",
                                         "options": "-csearch_path=tasteduel,pg_catalog"})
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            version_table="tasteduel_alembic_version",
            version_table_schema="tasteduel",
            include_schemas=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


run_migrations()
