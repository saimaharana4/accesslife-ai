"""Private short-lived provider response cache; never exposed by browser routes."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003_provider_cache"
down_revision = "0002"


def upgrade():
    op.create_table(
        "provider_cache",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_provider_cache_expires_at", "provider_cache", ["expires_at"])


def downgrade():
    op.drop_table("provider_cache")
