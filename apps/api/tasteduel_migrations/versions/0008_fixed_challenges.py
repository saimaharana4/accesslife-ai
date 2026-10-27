"""Exact delivered challenges and hash-scoped share capability."""

from alembic import op

revision = "td0008"
down_revision = "td0007"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
ALTER TABLE tasteduel.challenges ADD COLUMN share_slug varchar(80);
ALTER TABLE tasteduel.challenge_plays ADD COLUMN slug_hash varchar(64);
CREATE POLICY challenge_capability ON tasteduel.challenges FOR SELECT
 USING (slug_hash=nullif(current_setting('app.challenge_hash',true),''));
CREATE OR REPLACE FUNCTION tasteduel.freeze_challenge() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 INSERT INTO tasteduel.challenge_rounds(id,session_id,challenge_id,source_round_id,ordinal,snapshot_id,left_entity_id,right_entity_id,winner_entity_id)
 SELECT gen_random_uuid(),NEW.session_id,NEW.id,d.id,d.ordinal,p.snapshot_id,
 coalesce(d.left_entity_id,p.left_entity_id),coalesce(d.right_entity_id,p.right_entity_id),p.winner_entity_id
 FROM tasteduel.delivered_rounds d JOIN tasteduel.private_pairs p ON p.id=d.pair_id
 WHERE d.game_id=NEW.source_game_id AND d.session_id=NEW.session_id ORDER BY d.ordinal;
 IF (SELECT count(*) FROM tasteduel.challenge_rounds WHERE challenge_id=NEW.id)<>5 THEN
 RAISE EXCEPTION 'challenge requires five frozen rounds' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE OR REPLACE FUNCTION tasteduel.guard_challenge_round() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF pg_trigger_depth()<2 OR NOT EXISTS(SELECT 1 FROM tasteduel.challenges c
 JOIN tasteduel.delivered_rounds d ON d.game_id=c.source_game_id JOIN tasteduel.private_pairs p ON p.id=d.pair_id
 WHERE c.id=NEW.challenge_id AND c.session_id=NEW.session_id AND d.id=NEW.source_round_id AND d.ordinal=NEW.ordinal
 AND ROW(p.snapshot_id,coalesce(d.left_entity_id,p.left_entity_id),coalesce(d.right_entity_id,p.right_entity_id),p.winner_entity_id)
 =ROW(NEW.snapshot_id,NEW.left_entity_id,NEW.right_entity_id,NEW.winner_entity_id)) THEN
 RAISE EXCEPTION 'challenge round is not an authorized frozen copy' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
""")


def downgrade():
    raise RuntimeError("Use a reviewed forward migration; frozen challenges are retained.")
