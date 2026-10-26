"""Versioned private adaptive selection; preserve legacy delivered orientations."""

from alembic import op

revision = "td0007"
down_revision = "td0006"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
ALTER TABLE tasteduel.games ADD COLUMN selection_version varchar(80) NOT NULL DEFAULT 'fixed-path-v1';
ALTER TABLE tasteduel.games ADD COLUMN selection_seed varchar(64);
ALTER TABLE tasteduel.games ADD CONSTRAINT ck_game_selection CHECK(
 (selection_version='fixed-path-v1' AND selection_seed IS NULL) OR
 (selection_version='solo-performance-v1' AND mode='solo' AND selection_seed IS NOT NULL AND selection_seed ~ '^[a-f0-9]{64}$'));
ALTER TABLE tasteduel.private_pairs ADD COLUMN category_labels text[] NOT NULL DEFAULT '{}';
ALTER TABLE tasteduel.private_pairs ADD CONSTRAINT ck_pair_categories CHECK(
 cardinality(category_labels)<=10 AND array_position(category_labels,NULL) IS NULL);
ALTER TABLE tasteduel.delivered_rounds ADD COLUMN left_entity_id uuid;
ALTER TABLE tasteduel.delivered_rounds ADD COLUMN right_entity_id uuid;
ALTER TABLE tasteduel.delivered_rounds ADD COLUMN selection_context jsonb;
ALTER TABLE tasteduel.delivered_rounds ADD CONSTRAINT fk_delivery_left FOREIGN KEY(left_entity_id,session_id) REFERENCES tasteduel.entities(id,session_id);
ALTER TABLE tasteduel.delivered_rounds ADD CONSTRAINT fk_delivery_right FOREIGN KEY(right_entity_id,session_id) REFERENCES tasteduel.entities(id,session_id);
ALTER TABLE tasteduel.delivered_rounds ADD CONSTRAINT ck_delivery_orientation CHECK(
 (left_entity_id IS NULL AND right_entity_id IS NULL AND selection_context IS NULL) OR
 (left_entity_id IS NOT NULL AND right_entity_id IS NOT NULL AND left_entity_id<>right_entity_id
  AND jsonb_typeof(selection_context)='object' AND octet_length(selection_context::text)<=2048));
CREATE FUNCTION tasteduel.guard_selection_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF ROW(NEW.selection_version,NEW.selection_seed) IS DISTINCT FROM ROW(OLD.selection_version,OLD.selection_seed) THEN
  RAISE EXCEPTION 'selection policy and private seed are immutable' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER guard_selection_identity BEFORE UPDATE ON tasteduel.games FOR EACH ROW EXECUTE FUNCTION tasteduel.guard_selection_identity();
CREATE FUNCTION tasteduel.guard_adaptive_delivery() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE g tasteduel.games; p tasteduel.private_pairs;
BEGIN
 SELECT * INTO g FROM tasteduel.games WHERE id=NEW.game_id AND session_id=NEW.session_id;
 SELECT * INTO p FROM tasteduel.private_pairs WHERE id=NEW.pair_id AND session_id=NEW.session_id AND game_id=NEW.game_id;
 IF g.selection_version='solo-performance-v1' THEN
  IF NEW.left_entity_id IS NULL OR NEW.right_entity_id IS NULL
   OR NOT (NEW.left_entity_id IN (p.left_entity_id,p.right_entity_id) AND NEW.right_entity_id IN (p.left_entity_id,p.right_entity_id))
   OR NEW.selection_context->>'policy_version' IS DISTINCT FROM g.selection_version
   OR NEW.selection_context->>'selected_band' IS DISTINCT FROM p.difficulty
   OR coalesce(NEW.selection_context->>'requested_band','') NOT IN ('easy','medium','hard')
   OR coalesce(NEW.selection_context->>'reason','') NOT IN ('requested_band','scarce_feasible_band')
   OR NEW.selection_context->>'winner_side' IS DISTINCT FROM (CASE WHEN NEW.left_entity_id=p.winner_entity_id THEN 'left' ELSE 'right' END) THEN
   RAISE EXCEPTION 'adaptive delivery must freeze validated pair and policy' USING ERRCODE='23514';
  END IF;
 ELSIF NEW.left_entity_id IS NOT NULL OR NEW.right_entity_id IS NOT NULL OR NEW.selection_context IS NOT NULL THEN
  RAISE EXCEPTION 'legacy delivery retains original fixed orientation' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER guard_adaptive_delivery BEFORE INSERT ON tasteduel.delivered_rounds FOR EACH ROW EXECUTE FUNCTION tasteduel.guard_adaptive_delivery();
CREATE OR REPLACE FUNCTION tasteduel.guard_contestant() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM tasteduel.delivered_rounds d JOIN tasteduel.private_pairs p ON p.id=d.pair_id
  WHERE d.id=NEW.round_id AND d.session_id=NEW.session_id AND d.game_id=NEW.game_id
  AND NEW.entity_id=CASE WHEN NEW.side='left' THEN coalesce(d.left_entity_id,p.left_entity_id) ELSE coalesce(d.right_entity_id,p.right_entity_id) END) THEN
  RAISE EXCEPTION 'contestant is not the frozen side' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION tasteduel.guard_selection_identity(),tasteduel.guard_adaptive_delivery() FROM PUBLIC;
""")


def downgrade():
    raise RuntimeError("Taste Duel rollback requires a reviewed forward migration.")
