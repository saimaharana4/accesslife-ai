-- This revision is additive: td0001 remains byte-for-byte frozen after application.
GRANT SELECT ON tasteduel.tasteduel_alembic_version TO tasteduel_runtime;

CREATE FUNCTION tasteduel.guard_session_update() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (to_jsonb(NEW)-'revoked_at') IS DISTINCT FROM (to_jsonb(OLD)-'revoked_at')
    OR (OLD.revoked_at IS NOT NULL AND NEW.revoked_at IS DISTINCT FROM OLD.revoked_at)
    OR NEW.revoked_at IS NULL THEN
    RAISE EXCEPTION 'session identity and revocation are immutable' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER guard_session_update BEFORE UPDATE ON tasteduel.sessions FOR EACH ROW EXECUTE FUNCTION tasteduel.guard_session_update();

CREATE FUNCTION tasteduel.guard_pool_freeze() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE game_id uuid; seed_id uuid; current_number integer; phase text;
BEGIN
  IF TG_TABLE_NAME='ranking_snapshots' OR TG_TABLE_NAME='private_pairs' THEN
    game_id := NEW.game_id;
  ELSE
    SELECT s.game_id INTO game_id FROM tasteduel.ranking_snapshots s WHERE s.id=NEW.snapshot_id AND s.session_id=NEW.session_id;
  END IF;
  SELECT g.current_ordinal,g.seed_entity_id,g.status INTO current_number,seed_id,phase
    FROM tasteduel.games g WHERE g.id=game_id AND g.session_id=NEW.session_id FOR UPDATE;
  IF current_number IS NULL OR current_number<>0 OR phase NOT IN ('preparing','ready') THEN
    RAISE EXCEPTION 'ranking context and pool are frozen after first delivery' USING ERRCODE='23514';
  END IF;
  IF TG_TABLE_NAME='snapshot_candidates' THEN
    IF NEW.entity_id=seed_id THEN
      RAISE EXCEPTION 'seed cannot compete in its own duel' USING ERRCODE='23514';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER guard_pool_freeze BEFORE INSERT ON tasteduel.ranking_snapshots FOR EACH ROW EXECUTE FUNCTION tasteduel.guard_pool_freeze();
CREATE TRIGGER guard_pool_freeze BEFORE INSERT ON tasteduel.snapshot_candidates FOR EACH ROW EXECUTE FUNCTION tasteduel.guard_pool_freeze();
CREATE TRIGGER guard_pool_freeze BEFORE INSERT ON tasteduel.private_pairs FOR EACH ROW EXECUTE FUNCTION tasteduel.guard_pool_freeze();

REVOKE ALL ON FUNCTION tasteduel.guard_session_update(), tasteduel.guard_pool_freeze() FROM PUBLIC;
