-- Validation only; mutation handlers and canonical HTTP signatures remain later work.
CREATE FUNCTION tasteduel.validate_completed_mutation_receipt() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE authoritative_revision integer;
BEGIN
  IF NEW.status<>'completed' THEN RETURN NEW; END IF;
  IF NEW.subject_kind='game' THEN
    SELECT revision INTO authoritative_revision FROM tasteduel.games
      WHERE id=NEW.subject_id AND session_id=NEW.session_id FOR UPDATE;
    IF authoritative_revision IS NULL OR NEW.outcome_revision<>authoritative_revision THEN
      RAISE EXCEPTION 'completed mutation must capture authoritative game revision' USING ERRCODE='23514';
    END IF;
  END IF;
  IF NEW.operation='answer' AND NOT EXISTS (SELECT 1 FROM tasteduel.answers
    WHERE round_id=NEW.outcome_id AND game_id=NEW.subject_id AND session_id=NEW.session_id) THEN
    RAISE EXCEPTION 'completed answer mutation requires an accepted answer' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
-- Alphabetical order keeps td0003's immutable/composite ownership checks first.
CREATE TRIGGER validate_completed_mutation_receipt BEFORE INSERT OR UPDATE ON tasteduel.mutation_receipts
  FOR EACH ROW EXECUTE FUNCTION tasteduel.validate_completed_mutation_receipt();
REVOKE ALL ON FUNCTION tasteduel.validate_completed_mutation_receipt() FROM PUBLIC;
