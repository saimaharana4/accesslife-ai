"""Minimal private authoritative product accounting, no payload/identity fields."""

from alembic import op

revision = "td0010"
down_revision = "td0009"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE tasteduel.product_events (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      session_id uuid NOT NULL REFERENCES tasteduel.sessions(id) ON DELETE CASCADE,
      game_id uuid NOT NULL,
      subject_id uuid NOT NULL,
      event varchar(32) NOT NULL CHECK(event IN ('game_started','game_completed',
        'round_answered','replay','challenge_create','challenge_open','challenge_complete','discovery_saved')),
      source_mode varchar(12) NOT NULL CHECK(source_mode IN ('fixture','qloo')),
      cohort varchar(12) NOT NULL CHECK(cohort IN ('excluded','operational')),
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      expires_at timestamptz NOT NULL CHECK(expires_at>created_at AND expires_at<=created_at+interval '7 days 1 minute'),
      CONSTRAINT uq_product_events_session_event_subject UNIQUE(session_id,event,subject_id),
      FOREIGN KEY(game_id,session_id) REFERENCES tasteduel.games(id,session_id) ON DELETE CASCADE
    );
    CREATE INDEX ix_product_events_expiry ON tasteduel.product_events(expires_at);
    ALTER TABLE tasteduel.product_events ENABLE ROW LEVEL SECURITY;
    ALTER TABLE tasteduel.product_events FORCE ROW LEVEL SECURITY;
    CREATE POLICY product_event_owner ON tasteduel.product_events
      USING(session_id=nullif(current_setting('app.session_id',true),'')::uuid)
      WITH CHECK(session_id=nullif(current_setting('app.session_id',true),'')::uuid);
    REVOKE ALL ON tasteduel.product_events FROM PUBLIC;
    GRANT SELECT,INSERT,DELETE ON tasteduel.product_events TO tasteduel_runtime;
    """)


def downgrade():
    raise RuntimeError("Use a reviewed forward migration for accounting retention changes.")
