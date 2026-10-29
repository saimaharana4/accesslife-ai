"""Allow the compatibility API to insert replays without the new ordinal field."""

from alembic import op

revision = "td0014"
down_revision = "td0013"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE FUNCTION tasteduel.number_legacy_attempt() RETURNS trigger
    LANGUAGE plpgsql SET search_path=pg_catalog,tasteduel AS $$
    BEGIN
      IF NEW.attempt_number IS NULL THEN
        SELECT coalesce(max(attempt_number),0)+1 INTO NEW.attempt_number
          FROM tasteduel.challenge_plays WHERE challenge_id=NEW.challenge_id AND session_id=NEW.session_id;
      END IF;
      RETURN NEW;
    END $$;
    REVOKE ALL ON FUNCTION tasteduel.number_legacy_attempt() FROM PUBLIC;
    CREATE TRIGGER number_legacy_attempt BEFORE INSERT ON tasteduel.challenge_plays
      FOR EACH ROW EXECUTE FUNCTION tasteduel.number_legacy_attempt();
    """)


def downgrade():
    raise RuntimeError("Use a forward migration; preserve existing attempts.")
