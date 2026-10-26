"""Authoritative fenced generation and immutable curation evidence."""

from alembic import op

revision = "td0006"
down_revision = "td0005"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
ALTER TABLE tasteduel.curation_receipts DROP CONSTRAINT ck_curation_receipts_deterministic_requests;
ALTER TABLE tasteduel.curation_receipts ADD COLUMN full_receipt jsonb;
ALTER TABLE tasteduel.curation_receipts ADD CONSTRAINT ck_full_receipt_bound CHECK(full_receipt IS NULL OR (jsonb_typeof(full_receipt)='object' AND octet_length(full_receipt::text)<=65536));
ALTER TABLE tasteduel.private_pairs ADD COLUMN planned_ordinal integer CHECK(planned_ordinal BETWEEN 1 AND 5);
ALTER TABLE tasteduel.private_pairs ADD COLUMN left_choice_id uuid;
ALTER TABLE tasteduel.private_pairs ADD COLUMN right_choice_id uuid;
ALTER TABLE tasteduel.private_pairs ADD CONSTRAINT uq_private_pair_plan UNIQUE(game_id, planned_ordinal);
ALTER TABLE tasteduel.private_pairs ADD CONSTRAINT ck_private_pair_plan CHECK((planned_ordinal IS NULL AND left_choice_id IS NULL AND right_choice_id IS NULL) OR (planned_ordinal IS NOT NULL AND left_choice_id IS NOT NULL AND right_choice_id IS NOT NULL AND left_choice_id<>right_choice_id));
ALTER TABLE tasteduel.generation_reservations ADD COLUMN failure_code varchar(64);
CREATE OR REPLACE FUNCTION tasteduel.guard_receipt() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM tasteduel.games WHERE id=NEW.game_id AND session_id=NEW.session_id
   AND seed_entity_id=NEW.seed_entity_id AND seed_type=NEW.seed_type AND validator_version=NEW.validator_version) THEN
  RAISE EXCEPTION 'receipt does not describe its game' USING ERRCODE='23514';
 END IF;
 IF NEW.full_receipt IS NOT NULL AND (
   NEW.full_receipt->>'game_id' IS DISTINCT FROM NEW.game_id::text
   OR NEW.full_receipt->>'curator_mode' IS DISTINCT FROM NEW.curator_mode
   OR NEW.full_receipt->>'status' IS DISTINCT FROM NEW.status
   OR NEW.full_receipt->>'seed_type' IS DISTINCT FROM NEW.seed_type
   OR NEW.full_receipt->>'validator_version' IS DISTINCT FROM NEW.validator_version
   OR NEW.full_receipt->>'qloo_request_count' IS DISTINCT FROM NEW.qloo_request_count::text
   OR NEW.full_receipt->>'model_request_count' IS DISTINCT FROM NEW.model_request_count::text
   OR NEW.full_receipt->>'candidate_count_received' IS DISTINCT FROM NEW.candidate_count_received::text
   OR NEW.full_receipt->>'valid_pair_count' IS DISTINCT FROM NEW.valid_pair_count::text
   OR NEW.full_receipt->>'five_round_path_verified' IS DISTINCT FROM NEW.five_round_path_verified::text
   OR NEW.full_receipt->'target_domains_selected' IS DISTINCT FROM to_jsonb(NEW.target_domains_selected)
   OR NOT EXISTS(SELECT 1 FROM tasteduel.entities e WHERE e.id=NEW.seed_entity_id AND e.session_id=NEW.session_id
      AND e.provider_entity_id=NEW.full_receipt->>'seed_entity_id')) THEN
  RAISE EXCEPTION 'full receipt differs from authoritative evidence columns' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE FUNCTION tasteduel.guard_generation_claim() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='UPDATE' THEN
  IF ROW(NEW.id,NEW.session_id,NEW.game_id,NEW.operation,NEW.idempotency_key,NEW.input_hash,NEW.created_at)
    IS DISTINCT FROM ROW(OLD.id,OLD.session_id,OLD.game_id,OLD.operation,OLD.idempotency_key,OLD.input_hash,OLD.created_at)
    OR OLD.status IN ('succeeded','cancelled') THEN
   RAISE EXCEPTION 'generation identity or terminal result is immutable' USING ERRCODE='23514';
  END IF;
  IF NEW.status='running' AND (NEW.lease_owner IS DISTINCT FROM OLD.lease_owner OR OLD.status<>'running') THEN
   IF NEW.fence<>OLD.fence+1 OR NEW.attempt_count<>OLD.attempt_count+1
     OR (OLD.status='running' AND OLD.lease_expires_at>clock_timestamp()) THEN
    RAISE EXCEPTION 'generation claim is not reclaimable' USING ERRCODE='23514';
   END IF;
  ELSIF NEW.fence<>OLD.fence OR NEW.attempt_count<>OLD.attempt_count THEN
   RAISE EXCEPTION 'generation fence changes only on claim' USING ERRCODE='23514';
  END IF;
  IF NEW.status='succeeded' AND (OLD.status<>'running' OR OLD.lease_expires_at<=clock_timestamp()
    OR NOT EXISTS(SELECT 1 FROM tasteduel.curation_receipts r WHERE r.game_id=NEW.game_id AND r.session_id=NEW.session_id AND r.status='succeeded' AND r.full_receipt IS NOT NULL)
    OR NOT EXISTS(SELECT 1 FROM tasteduel.delivered_rounds d WHERE d.game_id=NEW.game_id AND d.session_id=NEW.session_id AND d.ordinal=1)) THEN
   RAISE EXCEPTION 'generation publication requires live claim and committed evidence' USING ERRCODE='23514';
  END IF;
 END IF;
 IF NEW.status='running' AND (NEW.lease_owner IS NULL OR NEW.lease_expires_at<=clock_timestamp() OR NEW.deadline_at>NEW.lease_expires_at) THEN
  RAISE EXCEPTION 'running generation requires a bounded lease' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER guard_generation_claim BEFORE INSERT OR UPDATE ON tasteduel.generation_reservations FOR EACH ROW EXECUTE FUNCTION tasteduel.guard_generation_claim();
REVOKE ALL ON FUNCTION tasteduel.guard_generation_claim() FROM PUBLIC;
-- A new retry key may alias an already accepted immutable mutation. It must
-- retain that mutation's original revision rather than the game's later one.
CREATE OR REPLACE FUNCTION tasteduel.validate_completed_mutation_receipt() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE authoritative_revision integer;
BEGIN
 IF NEW.status<>'completed' THEN RETURN NEW; END IF;
 IF NEW.subject_kind='game' THEN
  SELECT revision INTO authoritative_revision FROM tasteduel.games
    WHERE id=NEW.subject_id AND session_id=NEW.session_id FOR UPDATE;
  IF authoritative_revision IS NULL OR
   (NEW.outcome_revision<>authoritative_revision AND NOT EXISTS(
     SELECT 1 FROM tasteduel.mutation_receipts r WHERE r.session_id=NEW.session_id
     AND r.subject_id=NEW.subject_id AND r.operation=NEW.operation AND r.status='completed'
     AND r.outcome_id=NEW.outcome_id AND r.outcome_revision=NEW.outcome_revision
     AND NEW.operation IN ('answer','advance'))) THEN
   RAISE EXCEPTION 'completed mutation must capture authoritative revision or immutable accepted alias' USING ERRCODE='23514';
  END IF;
 END IF;
 IF NEW.operation='answer' AND NOT EXISTS(SELECT 1 FROM tasteduel.answers
   WHERE round_id=NEW.outcome_id AND game_id=NEW.subject_id AND session_id=NEW.session_id) THEN
  RAISE EXCEPTION 'completed answer mutation requires an accepted answer' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
""")


def downgrade():
    raise RuntimeError("Taste Duel rollback requires an explicitly reviewed forward migration.")
