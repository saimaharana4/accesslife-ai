-- The isolated bootstrap creates this schema owned by the migration role.
REVOKE ALL ON SCHEMA tasteduel FROM PUBLIC;

CREATE FUNCTION tasteduel.current_session_id() RETURNS uuid
LANGUAGE sql STABLE AS $$
  SELECT nullif(current_setting('app.session_id', true), '')::uuid
$$;

CREATE FUNCTION tasteduel.valid_domains(domains text[], allow_empty boolean) RETURNS boolean
LANGUAGE sql IMMUTABLE AS $$
  SELECT domains IS NOT NULL
    AND cardinality(domains) BETWEEN CASE WHEN allow_empty THEN 0 ELSE 1 END AND 2
    AND domains <@ ARRAY['artist','movie']::text[]
    AND NOT EXISTS (SELECT 1 FROM unnest(domains) x WHERE x IS NULL)
    AND cardinality(domains) = (SELECT count(DISTINCT x) FROM unnest(domains) x)
$$;

CREATE FUNCTION tasteduel.valid_rejections(counts jsonb, received integer) RETURNS boolean
LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE item record; total integer := 0;
BEGIN
  IF jsonb_typeof(counts) IS DISTINCT FROM 'object' THEN RETURN false; END IF;
  FOR item IN SELECT key, value FROM jsonb_each(counts) LOOP
    IF item.key NOT IN ('invalid_identity','wrong_type','self_pair','duplicate_entity',
       'missing_score','nonfinite_score','score_tie','near_tie','contradictory_order',
       'insufficient_metadata','unsupported_rights')
       OR jsonb_typeof(item.value) IS DISTINCT FROM 'number'
       OR item.value::text !~ '^[0-9]{1,4}$' THEN RETURN false; END IF;
    IF item.value::text::integer > 1000 THEN RETURN false; END IF;
    total := total + item.value::text::integer;
  END LOOP;
  RETURN total <= received;
END $$;



CREATE TABLE tasteduel.sessions (
	id UUID NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	revoked_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_sessions PRIMARY KEY (id), 
	CONSTRAINT ck_sessions_token_hash CHECK (token_hash ~ '^[a-f0-9]{64}$'), 
	CONSTRAINT ck_sessions_expiry CHECK (expires_at > created_at), 
	CONSTRAINT ck_sessions_revocation CHECK (revoked_at IS NULL OR revoked_at >= created_at), 
	CONSTRAINT uq_sessions_token_hash UNIQUE (token_hash)
)

;


CREATE TABLE tasteduel.entities (
	entity_type VARCHAR(16) NOT NULL, 
	name VARCHAR(300) NOT NULL, 
	provider VARCHAR(40) NOT NULL, 
	provider_entity_id VARCHAR(100) NOT NULL, 
	source_url VARCHAR(1000), 
	attribution VARCHAR(1000) NOT NULL, 
	rights_policy VARCHAR(100) NOT NULL, 
	artwork_asset_id VARCHAR(200), 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id UUID NOT NULL, 
	session_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_entities PRIMARY KEY (id), 
	CONSTRAINT uq_entities_id_session_id_entity_type UNIQUE (id, session_id, entity_type), 
	CONSTRAINT uq_entities_session_id_provider_provider_entity_id UNIQUE (session_id, provider, provider_entity_id), 
	CONSTRAINT ck_entities_type CHECK (entity_type IN ('artist','movie')), 
	CONSTRAINT ck_entities_name CHECK (length(name) BETWEEN 1 AND 300), 
	CONSTRAINT ck_entities_expiry CHECK (expires_at > created_at), 
	CONSTRAINT fk_entities_session_id_sessions FOREIGN KEY(session_id) REFERENCES tasteduel.sessions (id) ON DELETE CASCADE, 
	CONSTRAINT uq_entities_id_session_id UNIQUE (id, session_id)
)

;

CREATE INDEX ix_entities_session_id ON tasteduel.entities (session_id);


CREATE TABLE tasteduel.provider_cache (
	provider VARCHAR(40) NOT NULL, 
	key_hash VARCHAR(64) NOT NULL, 
	payload JSONB NOT NULL, 
	rights_policy VARCHAR(100) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id UUID NOT NULL, 
	session_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_provider_cache PRIMARY KEY (id), 
	CONSTRAINT uq_provider_cache_session_id_provider_key_hash UNIQUE (session_id, provider, key_hash), 
	CONSTRAINT ck_provider_cache_key_hash CHECK (key_hash ~ '^[a-f0-9]{64}$'), 
	CONSTRAINT ck_provider_cache_bounded_payload CHECK (octet_length(payload::text) <= 65536), 
	CONSTRAINT ck_provider_cache_expiry CHECK (expires_at > created_at), 
	CONSTRAINT fk_provider_cache_session_id_sessions FOREIGN KEY(session_id) REFERENCES tasteduel.sessions (id) ON DELETE CASCADE, 
	CONSTRAINT uq_provider_cache_id_session_id UNIQUE (id, session_id)
)

;

CREATE INDEX ix_provider_cache_session_id ON tasteduel.provider_cache (session_id);


CREATE TABLE tasteduel.usage_counters (
	scope VARCHAR(80) NOT NULL, 
	window_start TIMESTAMP WITH TIME ZONE NOT NULL, 
	window_end TIMESTAMP WITH TIME ZONE NOT NULL, 
	used INTEGER NOT NULL, 
	reserved INTEGER NOT NULL, 
	limit_value INTEGER NOT NULL, 
	id UUID NOT NULL, 
	session_id UUID NOT NULL, 
	CONSTRAINT pk_usage_counters PRIMARY KEY (id), 
	CONSTRAINT uq_usage_counters_session_id_scope_window_start UNIQUE (session_id, scope, window_start), 
	CONSTRAINT ck_usage_counters_bounds CHECK (used >= 0 AND reserved >= 0 AND used + reserved <= limit_value), 
	CONSTRAINT ck_usage_counters_window CHECK (window_end > window_start), 
	CONSTRAINT fk_usage_counters_session_id_sessions FOREIGN KEY(session_id) REFERENCES tasteduel.sessions (id) ON DELETE CASCADE, 
	CONSTRAINT uq_usage_counters_id_session_id UNIQUE (id, session_id)
)

;

CREATE INDEX ix_usage_counters_session_id ON tasteduel.usage_counters (session_id);


CREATE TABLE tasteduel.discoveries (
	entity_id UUID NOT NULL, 
	id UUID NOT NULL, 
	session_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_discoveries PRIMARY KEY (id), 
	CONSTRAINT fk_discoveries_entity_id_session_id_entities FOREIGN KEY(entity_id, session_id) REFERENCES tasteduel.entities (id, session_id), 
	CONSTRAINT uq_discoveries_session_id_entity_id UNIQUE (session_id, entity_id), 
	CONSTRAINT fk_discoveries_session_id_sessions FOREIGN KEY(session_id) REFERENCES tasteduel.sessions (id) ON DELETE CASCADE, 
	CONSTRAINT uq_discoveries_id_session_id UNIQUE (id, session_id)
)

;

CREATE INDEX ix_discoveries_session_id ON tasteduel.discoveries (session_id);


CREATE TABLE tasteduel.games (
	seed_entity_id UUID NOT NULL, 
	seed_type VARCHAR(16) NOT NULL, 
	mode VARCHAR(16) NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	current_ordinal INTEGER NOT NULL, 
	revision INTEGER NOT NULL, 
	scoring_version VARCHAR(80) NOT NULL, 
	validator_version VARCHAR(80) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id UUID NOT NULL, 
	session_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_games PRIMARY KEY (id), 
	CONSTRAINT fk_games_seed_entity_id_session_id_seed_type_entities FOREIGN KEY(seed_entity_id, session_id, seed_type) REFERENCES tasteduel.entities (id, session_id, entity_type), 
	CONSTRAINT ck_games_seed_type CHECK (seed_type IN ('artist','movie')), 
	CONSTRAINT ck_games_mode CHECK (mode IN ('solo','fixed')), 
	CONSTRAINT ck_games_status CHECK (status IN ('preparing','ready','playing','completed','expired','cancelled')), 
	CONSTRAINT ck_games_progress CHECK (current_ordinal BETWEEN 0 AND 5 AND revision >= 0), 
	CONSTRAINT ck_games_expiry CHECK (expires_at > created_at), 
	CONSTRAINT fk_games_session_id_sessions FOREIGN KEY(session_id) REFERENCES tasteduel.sessions (id) ON DELETE CASCADE, 
	CONSTRAINT uq_games_id_session_id UNIQUE (id, session_id)
)

;

CREATE INDEX ix_games_session_id ON tasteduel.games (session_id);


CREATE TABLE tasteduel.challenges (
	source_game_id UUID NOT NULL, 
	slug_hash VARCHAR(64) NOT NULL, 
	version INTEGER NOT NULL, 
	creator_score INTEGER NOT NULL, 
	scoring_version VARCHAR(80) NOT NULL, 
	validator_version VARCHAR(80) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	revoked_at TIMESTAMP WITH TIME ZONE, 
	id UUID NOT NULL, 
	session_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_challenges PRIMARY KEY (id), 
	CONSTRAINT fk_challenges_source_game_id_session_id_games FOREIGN KEY(source_game_id, session_id) REFERENCES tasteduel.games (id, session_id), 
	CONSTRAINT uq_challenges_slug_hash UNIQUE (slug_hash), 
	CONSTRAINT uq_challenges_source_game_id_version UNIQUE (source_game_id, version), 
	CONSTRAINT ck_challenges_slug_hash CHECK (slug_hash ~ '^[a-f0-9]{64}$'), 
	CONSTRAINT ck_challenges_version_score CHECK (version >= 1 AND creator_score BETWEEN 0 AND 5), 
	CONSTRAINT ck_challenges_expiry CHECK (expires_at > created_at), 
	CONSTRAINT fk_challenges_session_id_sessions FOREIGN KEY(session_id) REFERENCES tasteduel.sessions (id) ON DELETE CASCADE, 
	CONSTRAINT uq_challenges_id_session_id UNIQUE (id, session_id)
)

;

CREATE INDEX ix_challenges_session_id ON tasteduel.challenges (session_id);


CREATE TABLE tasteduel.curation_receipts (
	game_id UUID NOT NULL, 
	curator_mode VARCHAR(24) NOT NULL, 
	seed_entity_id UUID NOT NULL, 
	seed_type VARCHAR(16) NOT NULL, 
	target_domains_considered VARCHAR(16)[] NOT NULL, 
	target_domains_selected VARCHAR(16)[] NOT NULL, 
	qloo_request_count INTEGER NOT NULL, 
	tool_request_count INTEGER NOT NULL, 
	model_request_count INTEGER NOT NULL, 
	candidate_count_received INTEGER NOT NULL, 
	rejection_counts JSONB NOT NULL, 
	valid_pair_count INTEGER NOT NULL, 
	bounded_correction_count INTEGER NOT NULL, 
	five_round_path_verified BOOLEAN NOT NULL, 
	provider_version VARCHAR(80) NOT NULL, 
	harness_version VARCHAR(80), 
	model_version VARCHAR(80), 
	validator_version VARCHAR(80) NOT NULL, 
	elapsed_ms INTEGER NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	id UUID NOT NULL, 
	session_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_curation_receipts PRIMARY KEY (id), 
	CONSTRAINT fk_curation_receipts_game_id_session_id_games FOREIGN KEY(game_id, session_id) REFERENCES tasteduel.games (id, session_id), 
	CONSTRAINT fk_curation_receipts_seed_entity_id_session_id_seed_typ_390b FOREIGN KEY(seed_entity_id, session_id, seed_type) REFERENCES tasteduel.entities (id, session_id, entity_type), 
	CONSTRAINT uq_curation_receipts_game_id UNIQUE (game_id), 
	CONSTRAINT ck_curation_receipts_mode CHECK (curator_mode IN ('genuine_agent','deterministic_qloo','fixture')), 
	CONSTRAINT ck_curation_receipts_status CHECK (status IN ('succeeded','failed','partial','cancelled','timed_out')), 
	CONSTRAINT ck_curation_receipts_domains CHECK (tasteduel.valid_domains(target_domains_considered, false) AND tasteduel.valid_domains(target_domains_selected, true) AND target_domains_selected <@ target_domains_considered), 
	CONSTRAINT ck_curation_receipts_requests CHECK (qloo_request_count BETWEEN 0 AND 6 AND tool_request_count BETWEEN 0 AND 24 AND model_request_count BETWEEN 0 AND 4), 
	CONSTRAINT ck_curation_receipts_counts CHECK (candidate_count_received BETWEEN 0 AND 1000 AND valid_pair_count BETWEEN 0 AND 200 AND bounded_correction_count BETWEEN 0 AND 1 AND elapsed_ms BETWEEN 0 AND 120000), 
	CONSTRAINT ck_curation_receipts_rejections CHECK (tasteduel.valid_rejections(rejection_counts, candidate_count_received)), 
	CONSTRAINT ck_curation_receipts_fixture_requests CHECK (curator_mode <> 'fixture' OR (qloo_request_count = 0 AND model_request_count = 0)), 
	CONSTRAINT ck_curation_receipts_deterministic_requests CHECK (curator_mode <> 'deterministic_qloo' OR model_request_count = 0), 
	CONSTRAINT ck_curation_receipts_success CHECK (status <> 'succeeded' OR (five_round_path_verified AND valid_pair_count >= 5 AND candidate_count_received >= 10 AND cardinality(target_domains_selected) > 0)), 
	CONSTRAINT ck_curation_receipts_success_qloo CHECK (status <> 'succeeded' OR curator_mode = 'fixture' OR qloo_request_count > 0), 
	CONSTRAINT ck_curation_receipts_success_agent CHECK (status <> 'succeeded' OR curator_mode <> 'genuine_agent' OR (model_request_count > 0 AND model_version IS NOT NULL)), 
	CONSTRAINT fk_curation_receipts_session_id_sessions FOREIGN KEY(session_id) REFERENCES tasteduel.sessions (id) ON DELETE CASCADE, 
	CONSTRAINT uq_curation_receipts_id_session_id UNIQUE (id, session_id)
)

;

CREATE INDEX ix_curation_receipts_session_id ON tasteduel.curation_receipts (session_id);


CREATE TABLE tasteduel.game_results (
	game_id UUID NOT NULL, 
	score INTEGER NOT NULL, 
	scoring_version VARCHAR(80) NOT NULL, 
	id UUID NOT NULL, 
	session_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_game_results PRIMARY KEY (id), 
	CONSTRAINT fk_game_results_game_id_session_id_games FOREIGN KEY(game_id, session_id) REFERENCES tasteduel.games (id, session_id), 
	CONSTRAINT uq_game_results_game_id UNIQUE (game_id), 
	CONSTRAINT ck_game_results_score CHECK (score BETWEEN 0 AND 5), 
	CONSTRAINT fk_game_results_session_id_sessions FOREIGN KEY(session_id) REFERENCES tasteduel.sessions (id) ON DELETE CASCADE, 
	CONSTRAINT uq_game_results_id_session_id UNIQUE (id, session_id)
)

;

CREATE INDEX ix_game_results_session_id ON tasteduel.game_results (session_id);


CREATE TABLE tasteduel.generation_reservations (
	game_id UUID NOT NULL, 
	operation VARCHAR(40) NOT NULL, 
	idempotency_key VARCHAR(128) NOT NULL, 
	input_hash VARCHAR(64) NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	lease_owner UUID, 
	lease_expires_at TIMESTAMP WITH TIME ZONE, 
	fence INTEGER NOT NULL, 
	attempt_count INTEGER NOT NULL, 
	qloo_request_count INTEGER NOT NULL, 
	model_request_count INTEGER NOT NULL, 
	deadline_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id UUID NOT NULL, 
	session_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_generation_reservations PRIMARY KEY (id), 
	CONSTRAINT fk_generation_reservations_game_id_session_id_games FOREIGN KEY(game_id, session_id) REFERENCES tasteduel.games (id, session_id), 
	CONSTRAINT uq_generation_reservations_session_id_operation_idempotency_key UNIQUE (session_id, operation, idempotency_key), 
	CONSTRAINT uq_generation_reservations_game_id UNIQUE (game_id), 
	CONSTRAINT ck_generation_reservations_input_hash CHECK (input_hash ~ '^[a-f0-9]{64}$'), 
	CONSTRAINT ck_generation_reservations_status CHECK (status IN ('reserved','running','succeeded','failed','cancelled')), 
	CONSTRAINT ck_generation_reservations_lease_bounds CHECK (fence >= 0 AND attempt_count BETWEEN 0 AND 3), 
	CONSTRAINT ck_generation_reservations_lease_pair CHECK ((lease_owner IS NULL) = (lease_expires_at IS NULL)), 
	CONSTRAINT ck_generation_reservations_usage CHECK (qloo_request_count BETWEEN 0 AND 6 AND model_request_count BETWEEN 0 AND 4), 
	CONSTRAINT fk_generation_reservations_session_id_sessions FOREIGN KEY(session_id) REFERENCES tasteduel.sessions (id) ON DELETE CASCADE, 
	CONSTRAINT uq_generation_reservations_id_session_id UNIQUE (id, session_id)
)

;

CREATE INDEX ix_generation_reservations_session_id ON tasteduel.generation_reservations (session_id);


CREATE TABLE tasteduel.ranking_snapshots (
	game_id UUID NOT NULL, 
	target_type VARCHAR(16) NOT NULL, 
	query_context_hash VARCHAR(64) NOT NULL, 
	provider_version VARCHAR(80) NOT NULL, 
	harness_version VARCHAR(80), 
	score_semantics VARCHAR(300) NOT NULL, 
	attribution VARCHAR(1000) NOT NULL, 
	rights_policy VARCHAR(100) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	id UUID NOT NULL, 
	session_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_ranking_snapshots PRIMARY KEY (id), 
	CONSTRAINT fk_ranking_snapshots_game_id_session_id_games FOREIGN KEY(game_id, session_id) REFERENCES tasteduel.games (id, session_id), 
	CONSTRAINT uq_ranking_snapshots_id_session_id_target_type UNIQUE (id, session_id, target_type), 
	CONSTRAINT ck_ranking_snapshots_target_type CHECK (target_type IN ('artist','movie')), 
	CONSTRAINT ck_ranking_snapshots_context_hash CHECK (query_context_hash ~ '^[a-f0-9]{64}$'), 
	CONSTRAINT ck_ranking_snapshots_expiry CHECK (expires_at > created_at), 
	CONSTRAINT fk_ranking_snapshots_session_id_sessions FOREIGN KEY(session_id) REFERENCES tasteduel.sessions (id) ON DELETE CASCADE, 
	CONSTRAINT uq_ranking_snapshots_id_session_id UNIQUE (id, session_id)
)

;

CREATE INDEX ix_ranking_snapshots_session_id ON tasteduel.ranking_snapshots (session_id);


CREATE TABLE tasteduel.challenge_plays (
	challenge_id UUID NOT NULL, 
	game_id UUID NOT NULL, 
	id UUID NOT NULL, 
	session_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_challenge_plays PRIMARY KEY (id), 
	CONSTRAINT fk_challenge_plays_challenge_id_challenges FOREIGN KEY(challenge_id) REFERENCES tasteduel.challenges (id), 
	CONSTRAINT fk_challenge_plays_game_id_session_id_games FOREIGN KEY(game_id, session_id) REFERENCES tasteduel.games (id, session_id), 
	CONSTRAINT uq_challenge_plays_game_id UNIQUE (game_id), 
	CONSTRAINT fk_challenge_plays_session_id_sessions FOREIGN KEY(session_id) REFERENCES tasteduel.sessions (id) ON DELETE CASCADE, 
	CONSTRAINT uq_challenge_plays_id_session_id UNIQUE (id, session_id)
)

;

CREATE INDEX ix_challenge_plays_session_id ON tasteduel.challenge_plays (session_id);


CREATE TABLE tasteduel.snapshot_candidates (
	snapshot_id UUID NOT NULL, 
	entity_id UUID NOT NULL, 
	entity_type VARCHAR(16) NOT NULL, 
	rank INTEGER NOT NULL, 
	affinity FLOAT NOT NULL, 
	id UUID NOT NULL, 
	session_id UUID NOT NULL, 
	CONSTRAINT pk_snapshot_candidates PRIMARY KEY (id), 
	CONSTRAINT fk_snapshot_candidates_snapshot_id_session_id_entity_ty_4c6a FOREIGN KEY(snapshot_id, session_id, entity_type) REFERENCES tasteduel.ranking_snapshots (id, session_id, target_type), 
	CONSTRAINT fk_snapshot_candidates_entity_id_session_id_entity_type_23d3 FOREIGN KEY(entity_id, session_id, entity_type) REFERENCES tasteduel.entities (id, session_id, entity_type), 
	CONSTRAINT uq_snapshot_candidates_snapshot_id_session_id_entity_id UNIQUE (snapshot_id, session_id, entity_id), 
	CONSTRAINT uq_snapshot_candidates_snapshot_id_rank UNIQUE (snapshot_id, rank), 
	CONSTRAINT ck_snapshot_candidates_rank CHECK (rank > 0), 
	CONSTRAINT ck_snapshot_candidates_finite_affinity CHECK (affinity > '-Infinity'::float8 AND affinity < 'Infinity'::float8), 
	CONSTRAINT fk_snapshot_candidates_session_id_sessions FOREIGN KEY(session_id) REFERENCES tasteduel.sessions (id) ON DELETE CASCADE, 
	CONSTRAINT uq_snapshot_candidates_id_session_id UNIQUE (id, session_id)
)

;

CREATE INDEX ix_snapshot_candidates_session_id ON tasteduel.snapshot_candidates (session_id);


CREATE TABLE tasteduel.private_pairs (
	game_id UUID NOT NULL, 
	snapshot_id UUID NOT NULL, 
	left_entity_id UUID NOT NULL, 
	right_entity_id UUID NOT NULL, 
	winner_entity_id UUID NOT NULL, 
	difficulty VARCHAR(16) NOT NULL, 
	id UUID NOT NULL, 
	session_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_private_pairs PRIMARY KEY (id), 
	CONSTRAINT fk_private_pairs_game_id_session_id_games FOREIGN KEY(game_id, session_id) REFERENCES tasteduel.games (id, session_id), 
	CONSTRAINT fk_private_pairs_snapshot_id_session_id_ranking_snapshots FOREIGN KEY(snapshot_id, session_id) REFERENCES tasteduel.ranking_snapshots (id, session_id), 
	CONSTRAINT fk_pair_left_candidate FOREIGN KEY(snapshot_id, session_id, left_entity_id) REFERENCES tasteduel.snapshot_candidates (snapshot_id, session_id, entity_id), 
	CONSTRAINT fk_pair_right_candidate FOREIGN KEY(snapshot_id, session_id, right_entity_id) REFERENCES tasteduel.snapshot_candidates (snapshot_id, session_id, entity_id), 
	CONSTRAINT uq_private_pairs_id_session_id_game_id UNIQUE (id, session_id, game_id), 
	CONSTRAINT ck_private_pairs_contestants CHECK (left_entity_id <> right_entity_id AND winner_entity_id IN (left_entity_id,right_entity_id)), 
	CONSTRAINT ck_private_pairs_difficulty CHECK (difficulty IN ('easy','medium','hard')), 
	CONSTRAINT fk_private_pairs_session_id_sessions FOREIGN KEY(session_id) REFERENCES tasteduel.sessions (id) ON DELETE CASCADE, 
	CONSTRAINT uq_private_pairs_id_session_id UNIQUE (id, session_id)
)

;

CREATE INDEX ix_private_pairs_session_id ON tasteduel.private_pairs (session_id);


CREATE TABLE tasteduel.delivered_rounds (
	game_id UUID NOT NULL, 
	pair_id UUID NOT NULL, 
	ordinal INTEGER NOT NULL, 
	id UUID NOT NULL, 
	session_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_delivered_rounds PRIMARY KEY (id), 
	CONSTRAINT fk_delivered_rounds_game_id_session_id_games FOREIGN KEY(game_id, session_id) REFERENCES tasteduel.games (id, session_id), 
	CONSTRAINT fk_delivered_rounds_pair_id_session_id_game_id_private_pairs FOREIGN KEY(pair_id, session_id, game_id) REFERENCES tasteduel.private_pairs (id, session_id, game_id), 
	CONSTRAINT uq_delivered_rounds_id_session_id_game_id UNIQUE (id, session_id, game_id), 
	CONSTRAINT uq_delivered_rounds_game_id_ordinal UNIQUE (game_id, ordinal), 
	CONSTRAINT uq_delivered_rounds_game_id_pair_id UNIQUE (game_id, pair_id), 
	CONSTRAINT ck_delivered_rounds_ordinal CHECK (ordinal BETWEEN 1 AND 5), 
	CONSTRAINT fk_delivered_rounds_session_id_sessions FOREIGN KEY(session_id) REFERENCES tasteduel.sessions (id) ON DELETE CASCADE, 
	CONSTRAINT uq_delivered_rounds_id_session_id UNIQUE (id, session_id)
)

;

CREATE INDEX ix_delivered_rounds_session_id ON tasteduel.delivered_rounds (session_id);


CREATE TABLE tasteduel.challenge_rounds (
	challenge_id UUID NOT NULL, 
	source_round_id UUID NOT NULL, 
	ordinal INTEGER NOT NULL, 
	snapshot_id UUID NOT NULL, 
	left_entity_id UUID NOT NULL, 
	right_entity_id UUID NOT NULL, 
	winner_entity_id UUID NOT NULL, 
	id UUID NOT NULL, 
	session_id UUID NOT NULL, 
	CONSTRAINT pk_challenge_rounds PRIMARY KEY (id), 
	CONSTRAINT fk_challenge_rounds_challenge_id_session_id_challenges FOREIGN KEY(challenge_id, session_id) REFERENCES tasteduel.challenges (id, session_id), 
	CONSTRAINT fk_challenge_rounds_source_round_id_session_id_delivered_rounds FOREIGN KEY(source_round_id, session_id) REFERENCES tasteduel.delivered_rounds (id, session_id), 
	CONSTRAINT uq_challenge_rounds_challenge_id_ordinal UNIQUE (challenge_id, ordinal), 
	CONSTRAINT ck_challenge_rounds_ordinal CHECK (ordinal BETWEEN 1 AND 5), 
	CONSTRAINT fk_challenge_rounds_session_id_sessions FOREIGN KEY(session_id) REFERENCES tasteduel.sessions (id) ON DELETE CASCADE, 
	CONSTRAINT uq_challenge_rounds_id_session_id UNIQUE (id, session_id)
)

;

CREATE INDEX ix_challenge_rounds_session_id ON tasteduel.challenge_rounds (session_id);


CREATE TABLE tasteduel.round_contestants (
	game_id UUID NOT NULL, 
	round_id UUID NOT NULL, 
	entity_id UUID NOT NULL, 
	side VARCHAR(8) NOT NULL, 
	id UUID NOT NULL, 
	session_id UUID NOT NULL, 
	CONSTRAINT pk_round_contestants PRIMARY KEY (id), 
	CONSTRAINT fk_round_contestants_round_id_session_id_game_id_delive_8608 FOREIGN KEY(round_id, session_id, game_id) REFERENCES tasteduel.delivered_rounds (id, session_id, game_id), 
	CONSTRAINT fk_round_contestants_entity_id_session_id_entities FOREIGN KEY(entity_id, session_id) REFERENCES tasteduel.entities (id, session_id), 
	CONSTRAINT uq_round_contestants_round_id_side UNIQUE (round_id, side), 
	CONSTRAINT uq_round_contestants_round_id_entity_id UNIQUE (round_id, entity_id), 
	CONSTRAINT uq_round_contestants_game_id_entity_id UNIQUE (game_id, entity_id), 
	CONSTRAINT uq_round_contestants_id_session_id_round_id UNIQUE (id, session_id, round_id), 
	CONSTRAINT ck_round_contestants_side CHECK (side IN ('left','right')), 
	CONSTRAINT fk_round_contestants_session_id_sessions FOREIGN KEY(session_id) REFERENCES tasteduel.sessions (id) ON DELETE CASCADE, 
	CONSTRAINT uq_round_contestants_id_session_id UNIQUE (id, session_id)
)

;

CREATE INDEX ix_round_contestants_session_id ON tasteduel.round_contestants (session_id);


CREATE TABLE tasteduel.answers (
	game_id UUID NOT NULL, 
	round_id UUID NOT NULL, 
	choice_id UUID NOT NULL, 
	idempotency_key VARCHAR(128) NOT NULL, 
	correct BOOLEAN NOT NULL, 
	id UUID NOT NULL, 
	session_id UUID NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL, 
	CONSTRAINT pk_answers PRIMARY KEY (id), 
	CONSTRAINT fk_answers_round_id_session_id_game_id_delivered_rounds FOREIGN KEY(round_id, session_id, game_id) REFERENCES tasteduel.delivered_rounds (id, session_id, game_id), 
	CONSTRAINT fk_answers_choice_id_session_id_round_id_round_contestants FOREIGN KEY(choice_id, session_id, round_id) REFERENCES tasteduel.round_contestants (id, session_id, round_id), 
	CONSTRAINT uq_answers_round_id UNIQUE (round_id), 
	CONSTRAINT uq_answers_session_id_idempotency_key UNIQUE (session_id, idempotency_key), 
	CONSTRAINT fk_answers_session_id_sessions FOREIGN KEY(session_id) REFERENCES tasteduel.sessions (id) ON DELETE CASCADE, 
	CONSTRAINT uq_answers_id_session_id UNIQUE (id, session_id)
)

;

CREATE INDEX ix_answers_session_id ON tasteduel.answers (session_id);

-- Invoker functions preserve forced RLS; no SECURITY DEFINER escape hatch.
CREATE FUNCTION tasteduel.reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'immutable Taste Duel record' USING ERRCODE='23514'; END $$;

CREATE FUNCTION tasteduel.guard_game() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE evidence_expiry timestamptz;
BEGIN
  IF TG_OP='INSERT' THEN
    SELECT expires_at INTO evidence_expiry FROM tasteduel.entities WHERE id=NEW.seed_entity_id AND session_id=NEW.session_id;
    IF NEW.current_ordinal<>0 OR NEW.revision<>0 OR NEW.status<>'preparing' OR NEW.expires_at>evidence_expiry THEN
      RAISE EXCEPTION 'invalid initial game or evidence expiry' USING ERRCODE='23514';
    END IF;
  ELSE
    IF ROW(NEW.id,NEW.session_id,NEW.seed_entity_id,NEW.seed_type,NEW.mode,NEW.scoring_version,NEW.validator_version,NEW.created_at)
       IS DISTINCT FROM ROW(OLD.id,OLD.session_id,OLD.seed_entity_id,OLD.seed_type,OLD.mode,OLD.scoring_version,OLD.validator_version,OLD.created_at)
       OR NEW.expires_at>OLD.expires_at OR NEW.revision<>OLD.revision+1
       OR (pg_trigger_depth()<2 AND (NEW.current_ordinal<>OLD.current_ordinal OR NEW.status='completed')) THEN
      RAISE EXCEPTION 'invalid game transition' USING ERRCODE='23514';
    END IF;
    IF OLD.status IN ('completed','expired','cancelled') THEN
      RAISE EXCEPTION 'terminal game is immutable' USING ERRCODE='23514';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER guard_game BEFORE INSERT OR UPDATE ON tasteduel.games FOR EACH ROW EXECUTE FUNCTION tasteduel.guard_game();

CREATE FUNCTION tasteduel.guard_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM tasteduel.games g WHERE g.id=NEW.game_id AND g.session_id=NEW.session_id AND NEW.expires_at<=g.expires_at) THEN
    RAISE EXCEPTION 'snapshot exceeds game evidence expiry' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER guard_snapshot BEFORE INSERT ON tasteduel.ranking_snapshots FOR EACH ROW EXECUTE FUNCTION tasteduel.guard_snapshot();

CREATE FUNCTION tasteduel.guard_candidate() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM tasteduel.entities e JOIN tasteduel.ranking_snapshots s ON s.id=NEW.snapshot_id AND s.session_id=e.session_id
    WHERE e.id=NEW.entity_id AND e.session_id=NEW.session_id AND e.expires_at>=s.expires_at) THEN
    RAISE EXCEPTION 'candidate evidence expires before snapshot' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER guard_candidate BEFORE INSERT ON tasteduel.snapshot_candidates FOR EACH ROW EXECUTE FUNCTION tasteduel.guard_candidate();

CREATE FUNCTION tasteduel.guard_pair() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE l tasteduel.snapshot_candidates; r tasteduel.snapshot_candidates;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM tasteduel.ranking_snapshots WHERE id=NEW.snapshot_id AND session_id=NEW.session_id AND game_id=NEW.game_id) THEN
    RAISE EXCEPTION 'pair context belongs to another game' USING ERRCODE='23514';
  END IF;
  SELECT * INTO l FROM tasteduel.snapshot_candidates WHERE snapshot_id=NEW.snapshot_id AND session_id=NEW.session_id AND entity_id=NEW.left_entity_id;
  SELECT * INTO r FROM tasteduel.snapshot_candidates WHERE snapshot_id=NEW.snapshot_id AND session_id=NEW.session_id AND entity_id=NEW.right_entity_id;
  IF l.id IS NULL OR r.id IS NULL OR l.affinity=r.affinity OR
    (l.rank<r.rank AND (l.affinity<=r.affinity OR NEW.winner_entity_id<>l.entity_id)) OR
    (r.rank<l.rank AND (r.affinity<=l.affinity OR NEW.winner_entity_id<>r.entity_id)) THEN
    RAISE EXCEPTION 'pair requires a strict consistent same-context winner' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER guard_pair BEFORE INSERT ON tasteduel.private_pairs FOR EACH ROW EXECUTE FUNCTION tasteduel.guard_pair();

CREATE FUNCTION tasteduel.guard_delivery() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE g tasteduel.games;
BEGIN
  SELECT * INTO g FROM tasteduel.games WHERE id=NEW.game_id AND session_id=NEW.session_id FOR UPDATE;
  IF g.id IS NULL OR g.expires_at<=clock_timestamp() OR g.status NOT IN ('preparing','ready','playing') OR NEW.ordinal<>g.current_ordinal+1
    OR (g.current_ordinal>0 AND NOT EXISTS (SELECT 1 FROM tasteduel.answers a JOIN tasteduel.delivered_rounds d ON d.id=a.round_id
      WHERE d.game_id=g.id AND d.ordinal=g.current_ordinal))
    OR NOT EXISTS (SELECT 1 FROM tasteduel.private_pairs p JOIN tasteduel.ranking_snapshots s ON s.id=p.snapshot_id
      WHERE p.id=NEW.pair_id AND p.game_id=g.id AND p.session_id=NEW.session_id AND s.expires_at>clock_timestamp()) THEN
    RAISE EXCEPTION 'round delivery is not the next authorized live round' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER guard_delivery BEFORE INSERT ON tasteduel.delivered_rounds FOR EACH ROW EXECUTE FUNCTION tasteduel.guard_delivery();
CREATE FUNCTION tasteduel.record_delivery() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  UPDATE tasteduel.games SET current_ordinal=NEW.ordinal,revision=revision+1,status='playing' WHERE id=NEW.game_id AND session_id=NEW.session_id;
  RETURN NEW;
END $$;
CREATE TRIGGER record_delivery AFTER INSERT ON tasteduel.delivered_rounds FOR EACH ROW EXECUTE FUNCTION tasteduel.record_delivery();

CREATE FUNCTION tasteduel.guard_contestant() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM tasteduel.delivered_rounds d JOIN tasteduel.private_pairs p ON p.id=d.pair_id
    WHERE d.id=NEW.round_id AND d.session_id=NEW.session_id AND d.game_id=NEW.game_id
    AND NEW.entity_id=CASE WHEN NEW.side='left' THEN p.left_entity_id ELSE p.right_entity_id END) THEN
    RAISE EXCEPTION 'contestant is not the frozen side' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER guard_contestant BEFORE INSERT ON tasteduel.round_contestants FOR EACH ROW EXECUTE FUNCTION tasteduel.guard_contestant();
CREATE FUNCTION tasteduel.require_two_contestants() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (SELECT count(*) FROM tasteduel.round_contestants WHERE round_id=NEW.id AND session_id=NEW.session_id)<>2 THEN
    RAISE EXCEPTION 'delivered round must contain two frozen contestants at commit' USING ERRCODE='23514';
  END IF;
  RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER require_two_contestants AFTER INSERT ON tasteduel.delivered_rounds DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION tasteduel.require_two_contestants();

CREATE FUNCTION tasteduel.guard_answer() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE g tasteduel.games; chosen uuid; winner uuid; number integer;
BEGIN
  SELECT * INTO g FROM tasteduel.games WHERE id=NEW.game_id AND session_id=NEW.session_id FOR UPDATE;
  SELECT d.ordinal,p.winner_entity_id,c.entity_id INTO number,winner,chosen FROM tasteduel.delivered_rounds d
    JOIN tasteduel.private_pairs p ON p.id=d.pair_id JOIN tasteduel.round_contestants c ON c.round_id=d.id
    WHERE d.id=NEW.round_id AND d.session_id=NEW.session_id AND d.game_id=NEW.game_id AND c.id=NEW.choice_id;
  IF g.id IS NULL OR g.status<>'playing' OR g.expires_at<=clock_timestamp() OR number IS DISTINCT FROM g.current_ordinal
    OR (SELECT count(*) FROM tasteduel.round_contestants WHERE round_id=NEW.round_id)<>2 THEN
    RAISE EXCEPTION 'answer is not for the current live round' USING ERRCODE='23514';
  END IF;
  NEW.correct := chosen=winner;
  RETURN NEW;
END $$;
CREATE TRIGGER guard_answer BEFORE INSERT ON tasteduel.answers FOR EACH ROW EXECUTE FUNCTION tasteduel.guard_answer();
CREATE FUNCTION tasteduel.record_answer() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  UPDATE tasteduel.games SET revision=revision+1 WHERE id=NEW.game_id AND session_id=NEW.session_id;
  RETURN NEW;
END $$;
CREATE TRIGGER record_answer AFTER INSERT ON tasteduel.answers FOR EACH ROW EXECUTE FUNCTION tasteduel.record_answer();

CREATE FUNCTION tasteduel.guard_result() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE g tasteduel.games; accepted integer; actual integer;
BEGIN
  SELECT * INTO g FROM tasteduel.games WHERE id=NEW.game_id AND session_id=NEW.session_id FOR UPDATE;
  SELECT count(*),coalesce(sum(correct::integer),0) INTO accepted,actual FROM tasteduel.answers WHERE game_id=NEW.game_id AND session_id=NEW.session_id;
  IF g.status<>'playing' OR g.current_ordinal<>5 OR g.expires_at<=clock_timestamp() OR accepted<>5 OR NEW.score<>actual OR NEW.scoring_version<>g.scoring_version THEN
    RAISE EXCEPTION 'result requires five accepted answers and computed score' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER guard_result BEFORE INSERT ON tasteduel.game_results FOR EACH ROW EXECUTE FUNCTION tasteduel.guard_result();
CREATE FUNCTION tasteduel.record_result() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  UPDATE tasteduel.games SET status='completed',revision=revision+1 WHERE id=NEW.game_id AND session_id=NEW.session_id;
  RETURN NEW;
END $$;
CREATE TRIGGER record_result AFTER INSERT ON tasteduel.game_results FOR EACH ROW EXECUTE FUNCTION tasteduel.record_result();

CREATE FUNCTION tasteduel.guard_receipt() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM tasteduel.games WHERE id=NEW.game_id AND session_id=NEW.session_id AND seed_entity_id=NEW.seed_entity_id AND seed_type=NEW.seed_type AND validator_version=NEW.validator_version) THEN
    RAISE EXCEPTION 'receipt does not describe its game' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER guard_receipt BEFORE INSERT ON tasteduel.curation_receipts FOR EACH ROW EXECUTE FUNCTION tasteduel.guard_receipt();

CREATE FUNCTION tasteduel.guard_challenge() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE g tasteduel.games; source_score integer; evidence_expiry timestamptz;
BEGIN
  IF TG_OP='UPDATE' THEN
    IF (to_jsonb(NEW)-'revoked_at'-'expires_at') IS DISTINCT FROM (to_jsonb(OLD)-'revoked_at'-'expires_at')
      OR NEW.expires_at>OLD.expires_at OR (OLD.revoked_at IS NOT NULL AND NEW.revoked_at IS DISTINCT FROM OLD.revoked_at)
      OR (NEW.revoked_at IS NOT NULL AND NEW.revoked_at<NEW.created_at) THEN
      RAISE EXCEPTION 'challenge snapshot is immutable' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
  END IF;
  SELECT * INTO g FROM tasteduel.games WHERE id=NEW.source_game_id AND session_id=NEW.session_id FOR UPDATE;
  SELECT score INTO source_score FROM tasteduel.game_results WHERE game_id=g.id AND session_id=NEW.session_id;
  SELECT min(s.expires_at) INTO evidence_expiry FROM tasteduel.delivered_rounds d JOIN tasteduel.private_pairs p ON p.id=d.pair_id
    JOIN tasteduel.ranking_snapshots s ON s.id=p.snapshot_id WHERE d.game_id=g.id AND d.session_id=NEW.session_id;
  IF g.status IS DISTINCT FROM 'completed' OR source_score IS NULL OR NEW.creator_score<>source_score
    OR NEW.scoring_version<>g.scoring_version OR NEW.validator_version<>g.validator_version
    OR NEW.expires_at>g.expires_at OR NEW.expires_at>evidence_expiry THEN
    RAISE EXCEPTION 'challenge requires a completed source and bounded evidence lifetime' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER guard_challenge BEFORE INSERT OR UPDATE ON tasteduel.challenges FOR EACH ROW EXECUTE FUNCTION tasteduel.guard_challenge();
CREATE FUNCTION tasteduel.freeze_challenge() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO tasteduel.challenge_rounds(id,session_id,challenge_id,source_round_id,ordinal,snapshot_id,left_entity_id,right_entity_id,winner_entity_id)
    SELECT gen_random_uuid(),NEW.session_id,NEW.id,d.id,d.ordinal,p.snapshot_id,p.left_entity_id,p.right_entity_id,p.winner_entity_id
    FROM tasteduel.delivered_rounds d JOIN tasteduel.private_pairs p ON p.id=d.pair_id
    WHERE d.game_id=NEW.source_game_id AND d.session_id=NEW.session_id ORDER BY d.ordinal;
  IF (SELECT count(*) FROM tasteduel.challenge_rounds WHERE challenge_id=NEW.id)<>5 THEN
    RAISE EXCEPTION 'challenge requires five frozen rounds' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER freeze_challenge AFTER INSERT ON tasteduel.challenges FOR EACH ROW EXECUTE FUNCTION tasteduel.freeze_challenge();
CREATE FUNCTION tasteduel.guard_challenge_round() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF pg_trigger_depth()<2 OR NOT EXISTS (SELECT 1 FROM tasteduel.challenges c JOIN tasteduel.delivered_rounds d ON d.game_id=c.source_game_id
    JOIN tasteduel.private_pairs p ON p.id=d.pair_id WHERE c.id=NEW.challenge_id AND c.session_id=NEW.session_id AND d.id=NEW.source_round_id
    AND d.ordinal=NEW.ordinal AND ROW(p.snapshot_id,p.left_entity_id,p.right_entity_id,p.winner_entity_id)=ROW(NEW.snapshot_id,NEW.left_entity_id,NEW.right_entity_id,NEW.winner_entity_id)) THEN
    RAISE EXCEPTION 'challenge round is not an authorized frozen copy' USING ERRCODE='23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER guard_challenge_round BEFORE INSERT ON tasteduel.challenge_rounds FOR EACH ROW EXECUTE FUNCTION tasteduel.guard_challenge_round();

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['sessions','entities','games','generation_reservations','ranking_snapshots','snapshot_candidates','curation_receipts','private_pairs','delivered_rounds','round_contestants','answers','game_results','challenges','challenge_rounds','challenge_plays','discoveries','provider_cache','usage_counters'] LOOP
    EXECUTE format('ALTER TABLE tasteduel.%I ENABLE ROW LEVEL SECURITY',t);
    EXECUTE format('ALTER TABLE tasteduel.%I FORCE ROW LEVEL SECURITY',t);
    IF t='sessions' THEN
      EXECUTE 'CREATE POLICY session_owner ON tasteduel.sessions USING (id=tasteduel.current_session_id()) WITH CHECK (id=tasteduel.current_session_id())';
    ELSE
      EXECUTE format('CREATE POLICY session_owner ON tasteduel.%I USING (session_id=tasteduel.current_session_id() AND EXISTS (SELECT 1 FROM tasteduel.sessions s WHERE s.id=tasteduel.current_session_id() AND s.revoked_at IS NULL AND s.expires_at>clock_timestamp())) WITH CHECK (session_id=tasteduel.current_session_id() AND EXISTS (SELECT 1 FROM tasteduel.sessions s WHERE s.id=tasteduel.current_session_id() AND s.revoked_at IS NULL AND s.expires_at>clock_timestamp()))',t);
    END IF;
  END LOOP;
  FOREACH t IN ARRAY ARRAY['entities','ranking_snapshots','snapshot_candidates','curation_receipts','private_pairs','delivered_rounds','round_contestants','answers','game_results','challenge_rounds','challenge_plays'] LOOP
    EXECUTE format('CREATE TRIGGER immutable_record BEFORE UPDATE OR DELETE ON tasteduel.%I FOR EACH ROW EXECUTE FUNCTION tasteduel.reject_mutation()',t);
  END LOOP;
END $$;

REVOKE ALL ON ALL TABLES IN SCHEMA tasteduel FROM PUBLIC, tasteduel_runtime;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA tasteduel FROM PUBLIC;
GRANT USAGE ON SCHEMA tasteduel TO tasteduel_runtime;
GRANT EXECUTE ON FUNCTION tasteduel.current_session_id(), tasteduel.valid_domains(text[],boolean), tasteduel.valid_rejections(jsonb,integer) TO tasteduel_runtime;
GRANT SELECT,INSERT ON tasteduel.sessions,tasteduel.entities,tasteduel.games,tasteduel.generation_reservations,tasteduel.ranking_snapshots,tasteduel.snapshot_candidates,tasteduel.curation_receipts,tasteduel.private_pairs,tasteduel.delivered_rounds,tasteduel.round_contestants,tasteduel.answers,tasteduel.game_results,tasteduel.challenges,tasteduel.challenge_rounds,tasteduel.challenge_plays,tasteduel.discoveries,tasteduel.provider_cache,tasteduel.usage_counters TO tasteduel_runtime;
GRANT UPDATE ON tasteduel.games,tasteduel.generation_reservations,tasteduel.provider_cache,tasteduel.usage_counters TO tasteduel_runtime;
GRANT UPDATE(revoked_at) ON tasteduel.sessions TO tasteduel_runtime;
GRANT UPDATE(revoked_at,expires_at) ON tasteduel.challenges TO tasteduel_runtime;
GRANT DELETE ON tasteduel.discoveries,tasteduel.provider_cache,tasteduel.usage_counters TO tasteduel_runtime;
