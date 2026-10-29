"""Keep revoked-link guests on idle expiry, never accidentally on the hard TTL."""

from alembic import op

revision = "td0013"
down_revision = "td0012"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE OR REPLACE FUNCTION tasteduel.session_deadline(owner_ref uuid) RETURNS timestamptz
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,tasteduel AS $$
      SELECT least(s.expires_at,coalesce(greatest(
        CASE WHEN NOT EXISTS(SELECT 1 FROM tasteduel.challenges c WHERE c.session_id=s.id)
          AND NOT EXISTS(SELECT 1 FROM tasteduel.challenge_plays p WHERE p.session_id=s.id)
          OR EXISTS(SELECT 1 FROM tasteduel.games g WHERE g.session_id=s.id AND g.mode='solo'
            AND g.expires_at>statement_timestamp() AND NOT EXISTS(SELECT 1 FROM tasteduel.challenges c WHERE c.source_game_id=g.id))
          THEN s.last_activity_at+interval '1 hour' ELSE NULL END,
        (SELECT max(tasteduel.challenge_deadline(c.id)) FROM tasteduel.challenges c
          WHERE c.session_id=s.id OR EXISTS(SELECT 1 FROM tasteduel.challenge_plays p
            WHERE p.challenge_id=c.id AND p.session_id=s.id))),s.last_activity_at+interval '1 hour'))
      FROM tasteduel.sessions s WHERE s.id=owner_ref AND s.revoked_at IS NULL
    $$;
    """)


def downgrade():
    raise RuntimeError("Use a forward migration; preserve existing sessions.")
