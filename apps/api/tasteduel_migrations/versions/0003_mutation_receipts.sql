
CREATE TABLE tasteduel.mutation_receipts (
	operation VARCHAR(40) NOT NULL, 
	idempotency_key VARCHAR(128) NOT NULL, 
	signature_hash VARCHAR(64) NOT NULL, 
	subject_kind VARCHAR(16) NOT NULL, 
	subject_id UUID NOT NULL, 
	outcome_kind VARCHAR(16), 
	outcome_id UUID, 
	outcome_revision INTEGER NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id UUID NOT NULL, 
	session_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_mutation_receipts PRIMARY KEY (id), 
	CONSTRAINT uq_mutation_receipts_session_id_operation_idempotency_key UNIQUE (session_id, operation, idempotency_key), 
	CONSTRAINT ck_mutation_receipts_operation CHECK (operation IN ('answer','advance','save_discovery','create_challenge','play_challenge')), 
	CONSTRAINT ck_mutation_receipts_key CHECK (length(idempotency_key) BETWEEN 1 AND 128), 
	CONSTRAINT ck_mutation_receipts_signature CHECK (signature_hash ~ '^[a-f0-9]{64}$'), 
	CONSTRAINT ck_mutation_receipts_subject_kind CHECK (subject_kind IN ('game','entity')), 
	CONSTRAINT ck_mutation_receipts_subject_operation CHECK ((operation='save_discovery' AND subject_kind='entity') OR (operation<>'save_discovery' AND subject_kind='game')), 
	CONSTRAINT ck_mutation_receipts_status CHECK (status IN ('reserved','completed')), 
	CONSTRAINT ck_mutation_receipts_revision CHECK (outcome_revision >= 0), 
	CONSTRAINT ck_mutation_receipts_expiry CHECK (expires_at > created_at), 
	CONSTRAINT ck_mutation_receipts_typed_outcome CHECK ((status='reserved' AND outcome_kind IS NULL AND outcome_id IS NULL) OR (status='completed' AND outcome_id IS NOT NULL AND ((operation IN ('answer','advance') AND outcome_kind='round') OR (operation='save_discovery' AND outcome_kind='discovery') OR (operation='create_challenge' AND outcome_kind='challenge') OR (operation='play_challenge' AND outcome_kind='game')))), 
	CONSTRAINT fk_mutation_receipts_session_id_sessions FOREIGN KEY(session_id) REFERENCES tasteduel.sessions (id) ON DELETE CASCADE, 
	CONSTRAINT uq_mutation_receipts_id_session_id UNIQUE (id, session_id)
)

;
CREATE INDEX ix_mutation_receipts_session_id ON tasteduel.mutation_receipts (session_id);

CREATE FUNCTION tasteduel.guard_mutation_receipt() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE subject_expiry timestamptz; owned_outcome boolean := false;
BEGIN
  IF TG_OP='UPDATE' THEN
    IF ROW(NEW.id,NEW.session_id,NEW.operation,NEW.idempotency_key,NEW.signature_hash,NEW.subject_kind,NEW.subject_id,NEW.created_at)
       IS DISTINCT FROM ROW(OLD.id,OLD.session_id,OLD.operation,OLD.idempotency_key,OLD.signature_hash,OLD.subject_kind,OLD.subject_id,OLD.created_at)
       OR OLD.status='completed' OR NEW.status<>'completed' OR NEW.expires_at>OLD.expires_at OR NEW.outcome_revision<OLD.outcome_revision THEN
      RAISE EXCEPTION 'mutation signature and completed outcome are immutable' USING ERRCODE='23514';
    END IF;
  END IF;
  IF NEW.subject_kind='game' THEN
    SELECT expires_at INTO subject_expiry FROM tasteduel.games WHERE id=NEW.subject_id AND session_id=NEW.session_id;
  ELSE
    SELECT expires_at INTO subject_expiry FROM tasteduel.entities WHERE id=NEW.subject_id AND session_id=NEW.session_id;
  END IF;
  IF subject_expiry IS NULL THEN
    RAISE EXCEPTION 'mutation subject must belong to this session' USING ERRCODE='23503';
  END IF;
  IF NEW.expires_at>subject_expiry THEN
    RAISE EXCEPTION 'mutation receipt exceeds subject lifetime' USING ERRCODE='23514';
  END IF;
  IF NEW.status='completed' THEN
    CASE NEW.outcome_kind
      WHEN 'round' THEN SELECT EXISTS(SELECT 1 FROM tasteduel.delivered_rounds WHERE id=NEW.outcome_id AND session_id=NEW.session_id AND game_id=NEW.subject_id) INTO owned_outcome;
      WHEN 'discovery' THEN SELECT EXISTS(SELECT 1 FROM tasteduel.discoveries WHERE id=NEW.outcome_id AND session_id=NEW.session_id AND entity_id=NEW.subject_id) INTO owned_outcome;
      WHEN 'challenge' THEN SELECT EXISTS(SELECT 1 FROM tasteduel.challenges WHERE id=NEW.outcome_id AND session_id=NEW.session_id AND source_game_id=NEW.subject_id) INTO owned_outcome;
      WHEN 'game' THEN SELECT EXISTS(SELECT 1 FROM tasteduel.games WHERE id=NEW.outcome_id AND id=NEW.subject_id AND session_id=NEW.session_id) INTO owned_outcome;
      ELSE owned_outcome := false;
    END CASE;
    IF NOT owned_outcome THEN
      RAISE EXCEPTION 'mutation outcome must be a typed owned subject result' USING ERRCODE='23503';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER guard_mutation_receipt BEFORE INSERT OR UPDATE ON tasteduel.mutation_receipts FOR EACH ROW EXECUTE FUNCTION tasteduel.guard_mutation_receipt();
ALTER TABLE tasteduel.mutation_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasteduel.mutation_receipts FORCE ROW LEVEL SECURITY;
CREATE POLICY session_owner ON tasteduel.mutation_receipts
  USING (session_id=tasteduel.current_session_id() AND EXISTS (SELECT 1 FROM tasteduel.sessions s WHERE s.id=tasteduel.current_session_id() AND s.revoked_at IS NULL AND s.expires_at>clock_timestamp()))
  WITH CHECK (session_id=tasteduel.current_session_id() AND EXISTS (SELECT 1 FROM tasteduel.sessions s WHERE s.id=tasteduel.current_session_id() AND s.revoked_at IS NULL AND s.expires_at>clock_timestamp()));
REVOKE ALL ON tasteduel.mutation_receipts FROM PUBLIC, tasteduel_runtime;
REVOKE ALL ON FUNCTION tasteduel.guard_mutation_receipt() FROM PUBLIC;
GRANT SELECT,INSERT ON tasteduel.mutation_receipts TO tasteduel_runtime;
GRANT UPDATE(status,outcome_kind,outcome_id,outcome_revision,expires_at) ON tasteduel.mutation_receipts TO tasteduel_runtime;
