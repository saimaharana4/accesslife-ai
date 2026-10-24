"""Cross-process provider permits and bounded request/model usage."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"


def upgrade():
    op.create_table(
        "provider_permits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(80), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_provider_permits_run_id", "provider_permits", ["run_id"])
    op.create_index("ix_provider_permits_expires_at", "provider_permits", ["expires_at"])
    op.create_table(
        "request_quotas",
        sa.Column("id", sa.String(160), primary_key=True),
        sa.Column("count", sa.Integer, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("request_quotas")
    op.drop_table("provider_permits")
