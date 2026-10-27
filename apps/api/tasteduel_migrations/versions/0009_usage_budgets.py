"""Privacy scoped guest and provider admission, bounded current-window facts only."""

from alembic import op

revision = "td0009"
down_revision = "td0008"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE tasteduel.usage_budgets (
      scope_hash varchar(64) NOT NULL CHECK (scope_hash ~ '^[a-f0-9]{64}$'),
      bucket varchar(40) NOT NULL CHECK (bucket ~ '^[a-z-]{1,40}$'),
      window_start timestamptz NOT NULL,
      expires_at timestamptz NOT NULL CHECK(expires_at>window_start),
      used integer NOT NULL CHECK(used>=0),
      limit_value integer NOT NULL CHECK(limit_value BETWEEN 1 AND 10000000),
      PRIMARY KEY(scope_hash,bucket), CHECK(used<=limit_value)
    );
    ALTER TABLE tasteduel.usage_budgets ENABLE ROW LEVEL SECURITY;
    ALTER TABLE tasteduel.usage_budgets FORCE ROW LEVEL SECURITY;
    CREATE POLICY usage_scope ON tasteduel.usage_budgets
      USING (scope_hash=current_setting('app.usage_scope',true))
      WITH CHECK (scope_hash=current_setting('app.usage_scope',true));
    REVOKE ALL ON tasteduel.usage_budgets FROM PUBLIC;
    GRANT SELECT,INSERT,UPDATE ON tasteduel.usage_budgets TO tasteduel_runtime;
    """)


def downgrade():
    raise RuntimeError("Use a reviewed forward migration; do not delete admission history implicitly.")
