"""Isolated local Prompt 5 lineage. Never consumes legacy DATABASE_URL."""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import make_url

from tasteduel.persistence.models import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

url = os.environ.get("TASTEDUEL_MIGRATION_DATABASE_URL", "")
parsed = make_url(url) if url else None
if (
    parsed is None
    or parsed.drivername != "postgresql+psycopg"
    or parsed.host not in {"127.0.0.1", "localhost"}
    or parsed.port != 55435
    or parsed.database != "tasteduel_prompt5"
    or parsed.username != "tasteduel_migrator"
):
    raise RuntimeError("Taste Duel Prompt 5 migrations require the isolated local owner database.")


def run_migrations():
    if context.is_offline_mode():
        context.configure(
            url=url,
            target_metadata=Base.metadata,
            literal_binds=True,
            version_table="tasteduel_alembic_version",
            version_table_schema="tasteduel",
        )
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = create_engine(url, poolclass=pool.NullPool, hide_parameters=True)
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
