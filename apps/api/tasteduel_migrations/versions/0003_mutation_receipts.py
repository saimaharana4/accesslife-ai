"""Private durable mutation signatures without implementing mutation handlers."""

from pathlib import Path

from alembic import op

revision = "td0003"
down_revision = "td0002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(Path(__file__).with_suffix(".sql").read_text(encoding="utf-8"))


def downgrade():
    raise RuntimeError("Taste Duel rollback requires an explicitly reviewed forward migration.")
