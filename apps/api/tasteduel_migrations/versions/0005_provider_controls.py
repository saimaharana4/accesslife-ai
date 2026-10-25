"""Private key-wide admission control; no application/provider payload storage."""

from alembic import op

revision = "td0005"
down_revision = "td0004"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE tasteduel.provider_controls (
            scope_hash varchar(64) PRIMARY KEY CHECK (scope_hash ~ '^[a-f0-9]{64}$'),
            window_start timestamptz NOT NULL DEFAULT clock_timestamp(),
            used integer NOT NULL DEFAULT 0 CHECK (used >= 0),
            limit_value integer NOT NULL DEFAULT 30 CHECK (limit_value BETWEEN 1 AND 120),
            next_allowed_at timestamptz,
            failures integer NOT NULL DEFAULT 0 CHECK (failures BETWEEN 0 AND 1000),
            open_until timestamptz,
            auth_blocked boolean NOT NULL DEFAULT false
        );
        ALTER TABLE tasteduel.provider_controls ENABLE ROW LEVEL SECURITY;
        ALTER TABLE tasteduel.provider_controls FORCE ROW LEVEL SECURITY;
        CREATE POLICY provider_key_scope ON tasteduel.provider_controls
          USING (scope_hash = current_setting('app.provider_scope', true))
          WITH CHECK (scope_hash = current_setting('app.provider_scope', true));
        REVOKE ALL ON tasteduel.provider_controls FROM PUBLIC;
        GRANT SELECT, INSERT, UPDATE ON tasteduel.provider_controls TO tasteduel_runtime;
    """)


def downgrade():
    raise RuntimeError("Taste Duel rollback requires an explicitly reviewed forward migration.")
