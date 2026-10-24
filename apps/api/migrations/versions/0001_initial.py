"""Initial durable planning schema and retrieval extensions."""

from alembic import op
from accesslife.persistence.db import Base

revision = "0001"
down_revision = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(
        op.get_bind(),
        tables=[
            Base.metadata.tables[name]
            for name in ("sessions", "plans", "runs", "plan_versions", "run_events", "trips")
        ],
    )
    op.execute("""CREATE TABLE knowledge_chunks (
        id text PRIMARY KEY, city_id text NOT NULL, text text NOT NULL,
        source_url text NOT NULL, source_title text NOT NULL, corpus_version text NOT NULL,
        model_revision text NOT NULL, token_count integer NOT NULL CHECK (token_count <= 256),
        embedding vector(384) NOT NULL,
        search_vector tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
    )""")
    op.execute("CREATE INDEX knowledge_lexical_idx ON knowledge_chunks USING gin(search_vector)")
    op.execute(
        "CREATE TABLE place_locations (id text PRIMARY KEY, city_id text NOT NULL, location geography(Point,4326) NOT NULL)"
    )
    op.execute("CREATE INDEX place_location_idx ON place_locations USING gist(location)")


def downgrade():
    op.execute("DROP TABLE place_locations")
    op.execute("DROP TABLE knowledge_chunks")
    Base.metadata.drop_all(
        op.get_bind(),
        tables=[
            Base.metadata.tables[name]
            for name in ("sessions", "plans", "runs", "plan_versions", "run_events", "trips")
        ],
    )
