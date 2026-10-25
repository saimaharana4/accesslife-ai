"""Taste Duel relational foundation. No provider calls or public serialization.

The separate Alembic lineage installs PostgreSQL enforcement and forced RLS.
Every application transaction must set app.session_id after authenticating it.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Integer,
    MetaData,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SCHEMA = "tasteduel"


class Base(DeclarativeBase):
    metadata = MetaData(
        schema=SCHEMA,
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        },
    )


def owner_args(*constraints):
    return (
        ForeignKeyConstraint(["session_id"], [f"{SCHEMA}.sessions.id"], ondelete="CASCADE"),
        UniqueConstraint("id", "session_id"),
        *constraints,
    )


def owned_fk(fields, table, remote=None, **kwargs):
    return ForeignKeyConstraint(fields, [f"{SCHEMA}.{table}.{name}" for name in (remote or fields)], **kwargs)


class Owned:
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)


class Created:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("clock_timestamp()")
    )


class Session(Created, Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint("token_hash ~ '^[a-f0-9]{64}$'", name="token_hash"),
        CheckConstraint("expires_at > created_at", name="expiry"),
        CheckConstraint("revoked_at IS NULL OR revoked_at >= created_at", name="revocation"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Entity(Owned, Created, Base):
    __tablename__ = "entities"
    __table_args__ = owner_args(
        UniqueConstraint("id", "session_id", "entity_type"),
        UniqueConstraint("session_id", "provider", "provider_entity_id"),
        CheckConstraint("entity_type IN ('artist','movie')", name="type"),
        CheckConstraint("length(name) BETWEEN 1 AND 300", name="name"),
        CheckConstraint("expires_at > created_at", name="expiry"),
    )
    entity_type: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1000))
    attribution: Mapped[str] = mapped_column(String(1000), nullable=False)
    rights_policy: Mapped[str] = mapped_column(String(100), nullable=False)
    artwork_asset_id: Mapped[str | None] = mapped_column(String(200))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Game(Owned, Created, Base):
    __tablename__ = "games"
    __table_args__ = owner_args(
        owned_fk(
            ["seed_entity_id", "session_id", "seed_type"], "entities", ["id", "session_id", "entity_type"]
        ),
        CheckConstraint("seed_type IN ('artist','movie')", name="seed_type"),
        CheckConstraint("mode IN ('solo','fixed')", name="mode"),
        CheckConstraint(
            "status IN ('preparing','ready','playing','completed','expired','cancelled')", name="status"
        ),
        CheckConstraint("current_ordinal BETWEEN 0 AND 5 AND revision >= 0", name="progress"),
        CheckConstraint("expires_at > created_at", name="expiry"),
    )
    seed_entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    seed_type: Mapped[str] = mapped_column(String(16), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="solo")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="preparing")
    current_ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scoring_version: Mapped[str] = mapped_column(String(80), nullable=False)
    validator_version: Mapped[str] = mapped_column(String(80), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class GenerationReservation(Owned, Created, Base):
    __tablename__ = "generation_reservations"
    __table_args__ = owner_args(
        owned_fk(["game_id", "session_id"], "games", ["id", "session_id"]),
        UniqueConstraint("session_id", "operation", "idempotency_key"),
        UniqueConstraint("game_id"),
        CheckConstraint("input_hash ~ '^[a-f0-9]{64}$'", name="input_hash"),
        CheckConstraint("status IN ('reserved','running','succeeded','failed','cancelled')", name="status"),
        CheckConstraint("fence >= 0 AND attempt_count BETWEEN 0 AND 3", name="lease_bounds"),
        CheckConstraint("(lease_owner IS NULL) = (lease_expires_at IS NULL)", name="lease_pair"),
        CheckConstraint(
            "qloo_request_count BETWEEN 0 AND 6 AND model_request_count BETWEEN 0 AND 4", name="usage"
        ),
    )
    game_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    operation: Mapped[str] = mapped_column(String(40), nullable=False, default="create_game")
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="reserved")
    lease_owner: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qloo_request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    model_request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RankingSnapshot(Owned, Created, Base):
    __tablename__ = "ranking_snapshots"
    __table_args__ = owner_args(
        owned_fk(["game_id", "session_id"], "games", ["id", "session_id"]),
        UniqueConstraint("id", "session_id", "target_type"),
        CheckConstraint("target_type IN ('artist','movie')", name="target_type"),
        CheckConstraint("query_context_hash ~ '^[a-f0-9]{64}$'", name="context_hash"),
        CheckConstraint("expires_at > created_at", name="expiry"),
    )
    game_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    target_type: Mapped[str] = mapped_column(String(16), nullable=False)
    query_context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_version: Mapped[str] = mapped_column(String(80), nullable=False)
    harness_version: Mapped[str | None] = mapped_column(String(80))
    score_semantics: Mapped[str] = mapped_column(String(300), nullable=False)
    attribution: Mapped[str] = mapped_column(String(1000), nullable=False)
    rights_policy: Mapped[str] = mapped_column(String(100), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SnapshotCandidate(Owned, Base):
    __tablename__ = "snapshot_candidates"
    __table_args__ = owner_args(
        owned_fk(
            ["snapshot_id", "session_id", "entity_type"],
            "ranking_snapshots",
            ["id", "session_id", "target_type"],
        ),
        owned_fk(["entity_id", "session_id", "entity_type"], "entities", ["id", "session_id", "entity_type"]),
        UniqueConstraint("snapshot_id", "session_id", "entity_id"),
        UniqueConstraint("snapshot_id", "rank"),
        CheckConstraint("rank > 0", name="rank"),
        CheckConstraint(
            "affinity > '-Infinity'::float8 AND affinity < 'Infinity'::float8", name="finite_affinity"
        ),
    )
    snapshot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(16), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    affinity: Mapped[float] = mapped_column(Float, nullable=False)


class CurationReceipt(Owned, Created, Base):
    """Private structured audit only: no prompts, raw responses, pools or reasoning."""

    __tablename__ = "curation_receipts"
    __table_args__ = owner_args(
        owned_fk(["game_id", "session_id"], "games", ["id", "session_id"]),
        owned_fk(
            ["seed_entity_id", "session_id", "seed_type"], "entities", ["id", "session_id", "entity_type"]
        ),
        UniqueConstraint("game_id"),
        CheckConstraint("curator_mode IN ('genuine_agent','deterministic_qloo','fixture')", name="mode"),
        CheckConstraint("status IN ('succeeded','failed','partial','cancelled','timed_out')", name="status"),
        CheckConstraint(
            "tasteduel.valid_domains(target_domains_considered, false) AND tasteduel.valid_domains(target_domains_selected, true) AND target_domains_selected <@ target_domains_considered",
            name="domains",
        ),
        CheckConstraint(
            "qloo_request_count BETWEEN 0 AND 6 AND tool_request_count BETWEEN 0 AND 24 AND model_request_count BETWEEN 0 AND 4",
            name="requests",
        ),
        CheckConstraint(
            "candidate_count_received BETWEEN 0 AND 1000 AND valid_pair_count BETWEEN 0 AND 200 AND bounded_correction_count BETWEEN 0 AND 1 AND elapsed_ms BETWEEN 0 AND 120000",
            name="counts",
        ),
        CheckConstraint(
            "tasteduel.valid_rejections(rejection_counts, candidate_count_received)", name="rejections"
        ),
        CheckConstraint(
            "curator_mode <> 'fixture' OR (qloo_request_count = 0 AND model_request_count = 0)",
            name="fixture_requests",
        ),
        CheckConstraint(
            "curator_mode <> 'deterministic_qloo' OR model_request_count = 0", name="deterministic_requests"
        ),
        CheckConstraint(
            "status <> 'succeeded' OR (five_round_path_verified AND valid_pair_count >= 5 AND candidate_count_received >= 10 AND cardinality(target_domains_selected) > 0)",
            name="success",
        ),
        CheckConstraint(
            "status <> 'succeeded' OR curator_mode = 'fixture' OR qloo_request_count > 0", name="success_qloo"
        ),
        CheckConstraint(
            "status <> 'succeeded' OR curator_mode <> 'genuine_agent' OR (model_request_count > 0 AND model_version IS NOT NULL)",
            name="success_agent",
        ),
    )
    game_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    curator_mode: Mapped[str] = mapped_column(String(24), nullable=False)
    seed_entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    seed_type: Mapped[str] = mapped_column(String(16), nullable=False)
    target_domains_considered: Mapped[list[str]] = mapped_column(ARRAY(String(16)), nullable=False)
    target_domains_selected: Mapped[list[str]] = mapped_column(ARRAY(String(16)), nullable=False)
    qloo_request_count: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_request_count: Mapped[int] = mapped_column(Integer, nullable=False)
    model_request_count: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_count_received: Mapped[int] = mapped_column(Integer, nullable=False)
    rejection_counts: Mapped[dict[str, int]] = mapped_column(JSONB, nullable=False)
    valid_pair_count: Mapped[int] = mapped_column(Integer, nullable=False)
    bounded_correction_count: Mapped[int] = mapped_column(Integer, nullable=False)
    five_round_path_verified: Mapped[bool] = mapped_column(Boolean, nullable=False)
    provider_version: Mapped[str] = mapped_column(String(80), nullable=False)
    harness_version: Mapped[str | None] = mapped_column(String(80))
    model_version: Mapped[str | None] = mapped_column(String(80))
    validator_version: Mapped[str] = mapped_column(String(80), nullable=False)
    elapsed_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)


class PrivatePair(Owned, Created, Base):
    __tablename__ = "private_pairs"
    __table_args__ = owner_args(
        owned_fk(["game_id", "session_id"], "games", ["id", "session_id"]),
        owned_fk(["snapshot_id", "session_id"], "ranking_snapshots", ["id", "session_id"]),
        owned_fk(
            ["snapshot_id", "session_id", "left_entity_id"],
            "snapshot_candidates",
            ["snapshot_id", "session_id", "entity_id"],
            name="fk_pair_left_candidate",
        ),
        owned_fk(
            ["snapshot_id", "session_id", "right_entity_id"],
            "snapshot_candidates",
            ["snapshot_id", "session_id", "entity_id"],
            name="fk_pair_right_candidate",
        ),
        UniqueConstraint("id", "session_id", "game_id"),
        CheckConstraint(
            "left_entity_id <> right_entity_id AND winner_entity_id IN (left_entity_id,right_entity_id)",
            name="contestants",
        ),
        CheckConstraint("difficulty IN ('easy','medium','hard')", name="difficulty"),
    )
    game_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    snapshot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    left_entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    right_entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    winner_entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(16), nullable=False)


class DeliveredRound(Owned, Created, Base):
    __tablename__ = "delivered_rounds"
    __table_args__ = owner_args(
        owned_fk(["game_id", "session_id"], "games", ["id", "session_id"]),
        owned_fk(["pair_id", "session_id", "game_id"], "private_pairs", ["id", "session_id", "game_id"]),
        UniqueConstraint("id", "session_id", "game_id"),
        UniqueConstraint("game_id", "ordinal"),
        UniqueConstraint("game_id", "pair_id"),
        CheckConstraint("ordinal BETWEEN 1 AND 5", name="ordinal"),
    )
    game_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    pair_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)


class RoundContestant(Owned, Base):
    __tablename__ = "round_contestants"
    __table_args__ = owner_args(
        owned_fk(["round_id", "session_id", "game_id"], "delivered_rounds", ["id", "session_id", "game_id"]),
        owned_fk(["entity_id", "session_id"], "entities", ["id", "session_id"]),
        UniqueConstraint("round_id", "side"),
        UniqueConstraint("round_id", "entity_id"),
        UniqueConstraint("game_id", "entity_id"),
        UniqueConstraint("id", "session_id", "round_id"),
        CheckConstraint("side IN ('left','right')", name="side"),
    )
    game_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    round_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)


class Answer(Owned, Created, Base):
    __tablename__ = "answers"
    __table_args__ = owner_args(
        owned_fk(["round_id", "session_id", "game_id"], "delivered_rounds", ["id", "session_id", "game_id"]),
        owned_fk(
            ["choice_id", "session_id", "round_id"], "round_contestants", ["id", "session_id", "round_id"]
        ),
        UniqueConstraint("round_id"),
        UniqueConstraint("session_id", "idempotency_key"),
    )
    game_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    round_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    choice_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False)


class GameResult(Owned, Created, Base):
    __tablename__ = "game_results"
    __table_args__ = owner_args(
        owned_fk(["game_id", "session_id"], "games", ["id", "session_id"]),
        UniqueConstraint("game_id"),
        CheckConstraint("score BETWEEN 0 AND 5", name="score"),
    )
    game_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    scoring_version: Mapped[str] = mapped_column(String(80), nullable=False)


class Challenge(Owned, Created, Base):
    __tablename__ = "challenges"
    __table_args__ = owner_args(
        owned_fk(["source_game_id", "session_id"], "games", ["id", "session_id"]),
        UniqueConstraint("slug_hash"),
        UniqueConstraint("source_game_id", "version"),
        CheckConstraint("slug_hash ~ '^[a-f0-9]{64}$'", name="slug_hash"),
        CheckConstraint("version >= 1 AND creator_score BETWEEN 0 AND 5", name="version_score"),
        CheckConstraint("expires_at > created_at", name="expiry"),
    )
    source_game_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    slug_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    creator_score: Mapped[int] = mapped_column(Integer, nullable=False)
    scoring_version: Mapped[str] = mapped_column(String(80), nullable=False)
    validator_version: Mapped[str] = mapped_column(String(80), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChallengeRound(Owned, Base):
    __tablename__ = "challenge_rounds"
    __table_args__ = owner_args(
        owned_fk(["challenge_id", "session_id"], "challenges", ["id", "session_id"]),
        owned_fk(["source_round_id", "session_id"], "delivered_rounds", ["id", "session_id"]),
        UniqueConstraint("challenge_id", "ordinal"),
        CheckConstraint("ordinal BETWEEN 1 AND 5", name="ordinal"),
    )
    challenge_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_round_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    left_entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    right_entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    winner_entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)


class ChallengePlay(Owned, Created, Base):
    __tablename__ = "challenge_plays"
    __table_args__ = owner_args(
        # Intentional cross-owner share reference: it grants no SELECT on creator rows.
        owned_fk(["challenge_id"], "challenges", ["id"]),
        owned_fk(["game_id", "session_id"], "games", ["id", "session_id"]),
        UniqueConstraint("game_id"),
    )
    challenge_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    game_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)


class Discovery(Owned, Created, Base):
    __tablename__ = "discoveries"
    __table_args__ = owner_args(
        owned_fk(["entity_id", "session_id"], "entities", ["id", "session_id"]),
        UniqueConstraint("session_id", "entity_id"),
    )
    entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)


class ProviderCache(Owned, Created, Base):
    __tablename__ = "provider_cache"
    __table_args__ = owner_args(
        UniqueConstraint("session_id", "provider", "key_hash"),
        CheckConstraint("key_hash ~ '^[a-f0-9]{64}$'", name="key_hash"),
        CheckConstraint("octet_length(payload::text) <= 65536", name="bounded_payload"),
        CheckConstraint("expires_at > created_at", name="expiry"),
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    rights_policy: Mapped[str] = mapped_column(String(100), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UsageCounter(Owned, Base):
    __tablename__ = "usage_counters"
    __table_args__ = owner_args(
        UniqueConstraint("session_id", "scope", "window_start"),
        CheckConstraint("used >= 0 AND reserved >= 0 AND used + reserved <= limit_value", name="bounds"),
        CheckConstraint("window_end > window_start", name="window"),
    )
    scope: Mapped[str] = mapped_column(String(80), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    limit_value: Mapped[int] = mapped_column(Integer, nullable=False)


class MutationReceipt(Owned, Created, Base):
    """Private durable idempotency signature and typed reference, never a raw DTO."""

    __tablename__ = "mutation_receipts"
    __table_args__ = owner_args(
        UniqueConstraint("session_id", "operation", "idempotency_key"),
        CheckConstraint(
            "operation IN ('answer','advance','save_discovery','create_challenge','play_challenge')",
            name="operation",
        ),
        CheckConstraint("length(idempotency_key) BETWEEN 1 AND 128", name="key"),
        CheckConstraint("signature_hash ~ '^[a-f0-9]{64}$'", name="signature"),
        CheckConstraint("subject_kind IN ('game','entity')", name="subject_kind"),
        CheckConstraint(
            "(operation='save_discovery' AND subject_kind='entity') OR "
            "(operation<>'save_discovery' AND subject_kind='game')",
            name="subject_operation",
        ),
        CheckConstraint("status IN ('reserved','completed')", name="status"),
        CheckConstraint("outcome_revision >= 0", name="revision"),
        CheckConstraint("expires_at > created_at", name="expiry"),
        CheckConstraint(
            "(status='reserved' AND outcome_kind IS NULL AND outcome_id IS NULL) OR "
            "(status='completed' AND outcome_id IS NOT NULL AND "
            "((operation IN ('answer','advance') AND outcome_kind='round') OR "
            "(operation='save_discovery' AND outcome_kind='discovery') OR "
            "(operation='create_challenge' AND outcome_kind='challenge') OR "
            "(operation='play_challenge' AND outcome_kind='game')))",
            name="typed_outcome",
        ),
    )
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    signature_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    subject_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    outcome_kind: Mapped[str | None] = mapped_column(String(16))
    outcome_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    outcome_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="reserved")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProviderControl(Base):
    """Service-private per-key counters; scoped by app.provider_scope, not a guest."""

    __tablename__ = "provider_controls"
    __table_args__ = (
        CheckConstraint("scope_hash ~ '^[a-f0-9]{64}$'", name="scope_hash"),
        CheckConstraint("used >= 0", name="used"),
        CheckConstraint("limit_value BETWEEN 1 AND 120", name="limit_value"),
        CheckConstraint("failures BETWEEN 0 AND 1000", name="failures"),
    )
    scope_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("clock_timestamp()")
    )
    used: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    limit_value: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("30"))
    next_allowed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failures: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    open_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    auth_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))


# Descriptive aliases used by repository callers; no second set of mapped tables.
GuestSession = Session
AcceptedAnswer = Answer
PoolPair = PrivatePair
