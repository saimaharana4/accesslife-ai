"""Immutable Taste Duel foundation; separate from all AccessLife revisions."""

from pathlib import Path

from alembic import op

revision = "td0001"
down_revision = None
branch_labels = ("tasteduel",)
depends_on = None


def upgrade():
    # Static checked-in SQL is frozen with this revision, not imported ORM metadata.
    sql = Path(__file__).with_suffix(".sql").read_text(encoding="utf-8")
    op.execute(sql)


def downgrade():
    raise RuntimeError(
        "Foundation downgrade is destructive; use an explicitly reviewed disposable-database teardown."
    )
