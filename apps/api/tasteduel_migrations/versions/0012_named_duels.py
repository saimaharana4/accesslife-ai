"""Session nicknames and a narrow, participant-only completed-score projection."""

from alembic import op

revision = "td0012"
down_revision = "td0011"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    ALTER TABLE tasteduel.sessions ADD COLUMN display_name varchar(24)
      CHECK(display_name IS NULL OR (length(btrim(display_name)) BETWEEN 1 AND 24
        AND display_name=btrim(display_name)));
    ALTER TABLE tasteduel.sessions ADD COLUMN last_activity_at timestamptz NOT NULL DEFAULT clock_timestamp();
    ALTER TABLE tasteduel.challenge_plays ADD COLUMN attempt_number integer;
    -- Existing replays are immutable and forced-RLS applies to the migration
    -- owner too. Open only this column's NULL-to-positive backfill, inside the
    -- same migration transaction; restore both guards before proceeding.
    CREATE POLICY migration_attempt_backfill ON tasteduel.challenge_plays
      FOR UPDATE TO tasteduel_migrator
      USING(current_user='tasteduel_migrator' AND session_user='tasteduel_migrator'
        AND attempt_number IS NULL)
      WITH CHECK(current_user='tasteduel_migrator' AND session_user='tasteduel_migrator'
        AND attempt_number>0);
    ALTER TABLE tasteduel.challenge_plays DISABLE TRIGGER immutable_record;
    WITH numbered AS (SELECT id,row_number() OVER(PARTITION BY challenge_id,session_id ORDER BY created_at,id) n
      FROM tasteduel.challenge_plays) UPDATE tasteduel.challenge_plays p SET attempt_number=n.n FROM numbered n WHERE n.id=p.id;
    ALTER TABLE tasteduel.challenge_plays ENABLE TRIGGER immutable_record;
    DROP POLICY migration_attempt_backfill ON tasteduel.challenge_plays;
    ALTER TABLE tasteduel.challenge_plays ALTER COLUMN attempt_number SET NOT NULL;
    ALTER TABLE tasteduel.challenge_plays ADD CONSTRAINT uq_challenge_attempt
      UNIQUE(challenge_id,session_id,attempt_number);
    GRANT UPDATE(display_name) ON tasteduel.sessions TO tasteduel_runtime;
    GRANT UPDATE(last_activity_at) ON tasteduel.sessions TO tasteduel_runtime;
    CREATE OR REPLACE FUNCTION tasteduel.guard_session_update() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF (to_jsonb(NEW)-'revoked_at'-'display_name'-'last_activity_at') IS DISTINCT FROM
         (to_jsonb(OLD)-'revoked_at'-'display_name'-'last_activity_at')
        OR NEW.last_activity_at<OLD.last_activity_at OR NEW.last_activity_at>clock_timestamp()
        OR (OLD.revoked_at IS NOT NULL AND NEW.revoked_at IS DISTINCT FROM OLD.revoked_at)
        OR (NEW.revoked_at IS DISTINCT FROM OLD.revoked_at AND NEW.revoked_at IS NULL)
        OR (NEW.display_name IS DISTINCT FROM OLD.display_name AND
          (OLD.display_name IS NOT NULL OR OLD.revoked_at IS NOT NULL OR NEW.revoked_at IS NOT NULL
           OR OLD.expires_at<=clock_timestamp())) THEN
        RAISE EXCEPTION 'session identity and nickname are immutable' USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END $$;

    CREATE FUNCTION tasteduel.challenge_deadline(challenge_ref uuid) RETURNS timestamptz
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,tasteduel AS $$
      SELECT least(c.expires_at,s.expires_at, CASE
        WHEN EXISTS(SELECT 1 FROM tasteduel.challenge_plays p JOIN tasteduel.games g ON g.id=p.game_id
          JOIN tasteduel.sessions guest ON guest.id=p.session_id WHERE p.challenge_id=c.id
          AND g.status<>'completed' AND guest.revoked_at IS NULL AND guest.expires_at>statement_timestamp()
          AND g.expires_at>statement_timestamp())
          OR NOT EXISTS(SELECT 1 FROM tasteduel.challenge_plays p JOIN tasteduel.game_results r
            ON r.game_id=p.game_id WHERE p.challenge_id=c.id)
        THEN greatest(s.last_activity_at,coalesce((SELECT max(guest.last_activity_at)
          FROM tasteduel.challenge_plays p JOIN tasteduel.sessions guest ON guest.id=p.session_id
          WHERE p.challenge_id=c.id AND guest.revoked_at IS NULL),s.last_activity_at))+interval '1 hour'
        ELSE (SELECT max(r.created_at)+interval '10 minutes' FROM tasteduel.challenge_plays p
          JOIN tasteduel.game_results r ON r.game_id=p.game_id WHERE p.challenge_id=c.id) END)
      FROM tasteduel.challenges c JOIN tasteduel.sessions s ON s.id=c.session_id
      WHERE c.id=challenge_ref AND c.revoked_at IS NULL AND s.revoked_at IS NULL
    $$;

    CREATE FUNCTION tasteduel.session_deadline(owner_ref uuid) RETURNS timestamptz
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,tasteduel AS $$
      SELECT least(s.expires_at,greatest(
        CASE WHEN NOT EXISTS(SELECT 1 FROM tasteduel.challenges c WHERE c.session_id=s.id)
          AND NOT EXISTS(SELECT 1 FROM tasteduel.challenge_plays p WHERE p.session_id=s.id)
          OR EXISTS(SELECT 1 FROM tasteduel.games g WHERE g.session_id=s.id AND g.mode='solo'
            AND g.expires_at>statement_timestamp() AND NOT EXISTS(SELECT 1 FROM tasteduel.challenges c WHERE c.source_game_id=g.id))
          THEN s.last_activity_at+interval '1 hour' ELSE NULL END,
        (SELECT max(tasteduel.challenge_deadline(c.id)) FROM tasteduel.challenges c
          WHERE c.session_id=s.id OR EXISTS(SELECT 1 FROM tasteduel.challenge_plays p
            WHERE p.challenge_id=c.id AND p.session_id=s.id))))
      FROM tasteduel.sessions s WHERE s.id=owner_ref AND s.revoked_at IS NULL
    $$;
    CREATE FUNCTION tasteduel.session_live(owner_ref uuid) RETURNS boolean
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,tasteduel AS $$
      SELECT coalesce(tasteduel.session_deadline(owner_ref)>statement_timestamp(),false)
    $$;
    REVOKE ALL ON FUNCTION tasteduel.challenge_deadline(uuid),tasteduel.session_deadline(uuid),tasteduel.session_live(uuid) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION tasteduel.challenge_deadline(uuid),tasteduel.session_deadline(uuid),tasteduel.session_live(uuid) TO tasteduel_runtime;

    -- Keep the original conservative dependency checks, adding lifecycle expiry.
    ALTER FUNCTION tasteduel.maintenance_deletable(text,jsonb) RENAME TO maintenance_deletable_v11;
    CREATE FUNCTION tasteduel.maintenance_deletable(table_name text,row_data jsonb) RETURNS boolean
    LANGUAGE plpgsql STABLE SET search_path=pg_catalog,tasteduel AS $$
    DECLARE game_ref uuid;
    BEGIN
      IF current_user<>'tasteduel_migrator' OR session_user<>'tasteduel_migrator' THEN RETURN false; END IF;
      IF tasteduel.maintenance_deletable_v11(table_name,row_data) THEN RETURN true; END IF;
      IF table_name='sessions' THEN RETURN NOT tasteduel.session_live((row_data->>'id')::uuid); END IF;
      IF row_data->>'session_id' IS NOT NULL AND NOT tasteduel.session_live((row_data->>'session_id')::uuid) THEN RETURN true; END IF;
      IF table_name='challenges' THEN RETURN coalesce(tasteduel.challenge_deadline((row_data->>'id')::uuid)<=statement_timestamp(),true); END IF;
      IF row_data->>'challenge_id' IS NOT NULL AND coalesce(tasteduel.challenge_deadline((row_data->>'challenge_id')::uuid)<=statement_timestamp(),true) THEN RETURN true; END IF;
      game_ref:=CASE WHEN table_name='games' THEN (row_data->>'id')::uuid ELSE (row_data->>'game_id')::uuid END;
      IF game_ref IS NULL AND row_data->>'snapshot_id' IS NOT NULL THEN
        SELECT game_id INTO game_ref FROM tasteduel.ranking_snapshots WHERE id=(row_data->>'snapshot_id')::uuid;
      END IF;
      RETURN EXISTS(SELECT 1 FROM tasteduel.challenge_plays p WHERE p.game_id=game_ref
        AND coalesce(tasteduel.challenge_deadline(p.challenge_id)<=statement_timestamp(),true));
    END $$;
    REVOKE ALL ON FUNCTION tasteduel.maintenance_deletable(text,jsonb) FROM PUBLIC,tasteduel_runtime;
    GRANT EXECUTE ON FUNCTION tasteduel.maintenance_deletable(text,jsonb) TO tasteduel_migrator;
    DO $$ DECLARE t text; BEGIN
      FOREACH t IN ARRAY ARRAY['sessions','entities','games','generation_reservations','ranking_snapshots',
        'snapshot_candidates','curation_receipts','private_pairs','delivered_rounds','round_contestants',
        'answers','game_results','challenges','challenge_rounds','challenge_plays','discoveries',
        'provider_cache','usage_counters','mutation_receipts','product_events'] LOOP
        EXECUTE format('DROP POLICY maintenance_delete ON tasteduel.%I',t);
        EXECUTE format('CREATE POLICY maintenance_delete ON tasteduel.%I FOR DELETE TO tasteduel_migrator USING(tasteduel.maintenance_deletable(%L,to_jsonb(%I)))',t,t,t);
      END LOOP;
    END $$;
    CREATE POLICY maintenance_expire ON tasteduel.sessions FOR UPDATE TO tasteduel_migrator
      USING(NOT tasteduel.session_live(id)) WITH CHECK(revoked_at IS NOT NULL);
    CREATE POLICY maintenance_expired_budget ON tasteduel.usage_budgets FOR DELETE TO tasteduel_migrator
      USING(expires_at<=statement_timestamp());

    -- Runs as the migration owner, whose forced-RLS maintenance_read policies
    -- allow this fixed projection. It never returns answers, tokens or guest IDs.
    CREATE FUNCTION tasteduel.completed_duels(owned_game uuid)
    RETURNS TABLE(attempt_id uuid,attempt_number integer,completed_at timestamptz,
      creator_name varchar,challenger_name varchar,creator_score integer,challenger_score integer)
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,tasteduel AS $$
      SELECT p.id,p.attempt_number,r.created_at,creator.display_name,guest.display_name,c.creator_score,r.score
      FROM tasteduel.challenges c
      JOIN tasteduel.challenge_plays p ON p.challenge_id=c.id
      JOIN tasteduel.sessions creator ON creator.id=c.session_id
      JOIN tasteduel.sessions guest ON guest.id=p.session_id
      JOIN tasteduel.games g ON g.id=p.game_id AND g.session_id=p.session_id
      JOIN tasteduel.game_results r ON r.game_id=g.id AND r.session_id=p.session_id
      WHERE ((c.source_game_id=owned_game AND c.session_id=tasteduel.current_session_id())
        OR (p.game_id=owned_game AND p.session_id=tasteduel.current_session_id()))
        AND p.session_id<>c.session_id AND g.status='completed'
        AND c.revoked_at IS NULL AND creator.revoked_at IS NULL AND guest.revoked_at IS NULL
        AND tasteduel.challenge_deadline(c.id)>statement_timestamp()
        AND tasteduel.session_live(creator.id) AND tasteduel.session_live(guest.id)
        AND least(c.expires_at,creator.expires_at,guest.expires_at,g.expires_at)>statement_timestamp()
      ORDER BY r.created_at DESC,p.id DESC
    $$;
    REVOKE ALL ON FUNCTION tasteduel.completed_duels(uuid) FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION tasteduel.completed_duels(uuid) TO tasteduel_runtime;
    CREATE INDEX ix_challenge_plays_challenge_id ON tasteduel.challenge_plays(challenge_id);
    CREATE INDEX ix_sessions_expires_at ON tasteduel.sessions(expires_at);
    CREATE INDEX ix_sessions_activity ON tasteduel.sessions(last_activity_at);
    """)


def downgrade():
    raise RuntimeError("Use a forward migration; preserve active games and sessions.")
