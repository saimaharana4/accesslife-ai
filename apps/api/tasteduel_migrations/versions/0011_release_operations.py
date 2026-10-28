"""Role-restricted expiry maintenance and hash-only expired-link tombstones."""

from alembic import op

revision = "td0011"
down_revision = "td0010"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    ALTER TABLE tasteduel.challenge_plays DROP CONSTRAINT fk_challenge_plays_game_id_session_id_games;
    ALTER TABLE tasteduel.challenge_plays ADD CONSTRAINT fk_challenge_plays_game_id_session_id_games
      FOREIGN KEY(game_id,session_id) REFERENCES tasteduel.games(id,session_id) ON DELETE CASCADE;
    CREATE TABLE tasteduel.challenge_tombstones (
      slug_hash varchar(64) PRIMARY KEY CHECK(slug_hash ~ '^[a-f0-9]{64}$'),
      reason varchar(16) NOT NULL CHECK(reason IN ('expired','revoked')),
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      expires_at timestamptz NOT NULL CHECK(expires_at>created_at AND expires_at<=created_at+interval '7 days 1 minute')
    );
    ALTER TABLE tasteduel.challenge_tombstones ENABLE ROW LEVEL SECURITY;
    ALTER TABLE tasteduel.challenge_tombstones FORCE ROW LEVEL SECURITY;
    CREATE POLICY capability ON tasteduel.challenge_tombstones FOR SELECT TO tasteduel_runtime
      USING(slug_hash=nullif(current_setting('app.challenge_hash',true),''));
    CREATE POLICY maintenance ON tasteduel.challenge_tombstones TO tasteduel_migrator
      USING(true) WITH CHECK(true);
    REVOKE ALL ON tasteduel.challenge_tombstones FROM PUBLIC,tasteduel_runtime;
    GRANT SELECT ON tasteduel.challenge_tombstones TO tasteduel_runtime;

    CREATE FUNCTION tasteduel.maintenance_deletable(table_name text, row_data jsonb)
    RETURNS boolean LANGUAGE plpgsql STABLE SET search_path=tasteduel,pg_catalog AS $$
    DECLARE game_ref uuid;
    BEGIN
      IF current_user<>'tasteduel_migrator' OR session_user<>'tasteduel_migrator' THEN RETURN false; END IF;
      IF (row_data->>'expires_at')::timestamptz<=statement_timestamp()
        OR row_data->>'revoked_at' IS NOT NULL
        OR (table_name='usage_counters' AND (row_data->>'window_end')::timestamptz<=statement_timestamp())
        THEN RETURN true; END IF;
      IF EXISTS(SELECT 1 FROM tasteduel.sessions s WHERE s.id=(row_data->>'session_id')::uuid
        AND (s.expires_at<=statement_timestamp() OR s.revoked_at IS NOT NULL)) THEN RETURN true; END IF;
      game_ref:=CASE WHEN table_name='games' THEN (row_data->>'id')::uuid ELSE (row_data->>'game_id')::uuid END;
      IF game_ref IS NULL AND row_data->>'snapshot_id' IS NOT NULL THEN
        SELECT game_id INTO game_ref FROM tasteduel.ranking_snapshots WHERE id=(row_data->>'snapshot_id')::uuid;
      END IF;
      IF EXISTS(SELECT 1 FROM tasteduel.games g WHERE g.id=game_ref AND g.expires_at<=statement_timestamp())
        OR EXISTS(SELECT 1 FROM tasteduel.challenge_plays p JOIN tasteduel.challenges c ON c.id=p.challenge_id
          JOIN tasteduel.sessions s ON s.id=c.session_id WHERE p.game_id=game_ref
          AND (c.expires_at<=statement_timestamp() OR c.revoked_at IS NOT NULL OR s.revoked_at IS NOT NULL OR s.expires_at<=statement_timestamp()))
        THEN RETURN true; END IF;
      IF EXISTS(SELECT 1 FROM tasteduel.ranking_snapshots r JOIN tasteduel.games g ON g.id=r.game_id
        WHERE r.id=(row_data->>'snapshot_id')::uuid AND (r.expires_at<=statement_timestamp() OR g.expires_at<=statement_timestamp()))
        THEN RETURN true; END IF;
      IF EXISTS(SELECT 1 FROM tasteduel.challenges c JOIN tasteduel.sessions s ON s.id=c.session_id
        WHERE c.id=(row_data->>'challenge_id')::uuid
        AND (c.expires_at<=statement_timestamp() OR c.revoked_at IS NOT NULL OR s.revoked_at IS NOT NULL OR s.expires_at<=statement_timestamp()))
        THEN RETURN true; END IF;
      IF table_name='discoveries' AND EXISTS(SELECT 1 FROM tasteduel.entities e
        WHERE e.id=(row_data->>'entity_id')::uuid AND e.expires_at<=statement_timestamp()) THEN RETURN true; END IF;
      RETURN false;
    END $$;
    REVOKE ALL ON FUNCTION tasteduel.maintenance_deletable(text,jsonb) FROM PUBLIC,tasteduel_runtime;
    GRANT EXECUTE ON FUNCTION tasteduel.maintenance_deletable(text,jsonb) TO tasteduel_migrator;

    CREATE OR REPLACE FUNCTION tasteduel.reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP='DELETE' AND current_user='tasteduel_migrator' AND session_user='tasteduel_migrator' THEN
        IF tasteduel.maintenance_deletable(TG_TABLE_NAME,to_jsonb(OLD)) THEN RETURN OLD; END IF;
      END IF;
      RAISE EXCEPTION 'immutable Taste Duel record' USING ERRCODE='23514';
    END $$;
    REVOKE ALL ON FUNCTION tasteduel.reject_mutation() FROM PUBLIC,tasteduel_runtime;

    DO $$ DECLARE t text; BEGIN
      FOREACH t IN ARRAY ARRAY['sessions','entities','games','generation_reservations','ranking_snapshots',
        'snapshot_candidates','curation_receipts','private_pairs','delivered_rounds','round_contestants',
        'answers','game_results','challenges','challenge_rounds','challenge_plays','discoveries',
        'provider_cache','usage_counters','mutation_receipts','product_events'] LOOP
        EXECUTE format('CREATE POLICY maintenance_read ON tasteduel.%I FOR SELECT TO tasteduel_migrator USING(true)',t);
        EXECUTE format('CREATE POLICY maintenance_delete ON tasteduel.%I FOR DELETE TO tasteduel_migrator USING(tasteduel.maintenance_deletable(%L,to_jsonb(%I)))',t,t,t);
      END LOOP;
    END $$;
    CREATE POLICY maintenance_read ON tasteduel.usage_budgets FOR SELECT TO tasteduel_migrator USING(true);
    CREATE POLICY maintenance_budget ON tasteduel.usage_budgets FOR UPDATE TO tasteduel_migrator
      USING(bucket IN ('vertex-requests-day','vertex-tokens-day','qloo-requests-day'))
      WITH CHECK((bucket='vertex-requests-day' AND limit_value<=50) OR (bucket='qloo-requests-day' AND limit_value<=100)
        OR (bucket='vertex-tokens-day' AND limit_value=500000));
    """)


def downgrade():
    raise RuntimeError("Expiry maintenance is forward-only; retain existing data.")
