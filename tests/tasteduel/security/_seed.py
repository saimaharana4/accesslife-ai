"""Independent synthetic private graph; never a catalogue or provider response."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.orm import Session as DbSession

from tasteduel.persistence import models as m
from tasteduel.persistence.db import scoped_session


@dataclass(frozen=True)
class PrivateGraph:
    owner_id: UUID
    game_id: UUID
    snapshot_id: UUID
    seed_id: UUID
    first_pair_id: UUID
    first_round_id: UUID
    first_left_choice_id: UUID
    first_right_choice_id: UUID
    future_entity_ids: tuple[UUID, ...]
    future_pair_ids: tuple[UUID, ...]
    future_names: tuple[str, ...]
    private_markers: tuple[str, ...]


def seed_private_graph(engine, owner_id: UUID, *, answered: bool = False) -> PrivateGraph:
    """Attach a pool to an authenticated existing session, with one delivered round.

    Flush in real FK/trigger order. PostgreSQL, rather than this helper, derives
    the game revision/current state and accepted answer correctness.
    """
    expiry = datetime.now(UTC) + timedelta(hours=1)
    private_markers = (
        "SYNTHETIC_PRIVATE_SCORE_SEMANTICS",
        "SYNTHETIC_PRIVATE_PROVIDER_VERSION",
        "SYNTHETIC_PRIVATE_VALIDATOR_VERSION",
        "SYNTHETIC_RAW_PROVIDER_PAYLOAD",
    )
    future_names = tuple(f"PRIVATE_FUTURE_CONTESTANT_{number}" for number in range(3, 11))
    with scoped_session(engine, owner_id) as db:
        seed = m.Entity(
            id=uuid4(),
            session_id=owner_id,
            entity_type="artist",
            name="Synthetic Cultural Seed",
            provider="fixture",
            provider_entity_id="security-seed",
            attribution="Project-owned test data",
            rights_policy="project_owned",
            expires_at=expiry,
        )
        db.add(seed)
        contestants = []
        for index, name in enumerate(("Synthetic Current Right", "Synthetic Current Left", *future_names)):
            entity = m.Entity(
                id=uuid4(),
                session_id=owner_id,
                entity_type="movie",
                name=name,
                provider="fixture",
                provider_entity_id=f"security-contestant-{index}",
                source_url=f"https://example.invalid/private-source-{index}",
                attribution="Project-owned test data",
                rights_policy="project_owned",
                expires_at=expiry,
            )
            db.add(entity)
            contestants.append(entity)
        db.flush()
        game = m.Game(
            id=uuid4(),
            session_id=owner_id,
            seed_entity_id=seed.id,
            seed_type="artist",
            mode="solo",
            status="preparing",
            current_ordinal=0,
            revision=0,
            scoring_version="synthetic-score-v1",
            validator_version=private_markers[2],
            expires_at=expiry,
        )
        db.add(game)
        db.flush()
        snapshot = m.RankingSnapshot(
            id=uuid4(),
            session_id=owner_id,
            game_id=game.id,
            target_type="movie",
            query_context_hash=hashlib.sha256(b"synthetic-private-context").hexdigest(),
            provider_version=private_markers[1],
            score_semantics=private_markers[0],
            attribution="Project-owned test data",
            rights_policy="project_owned",
            expires_at=expiry,
        )
        db.add(snapshot)
        db.flush()
        for index, entity in enumerate(contestants):
            db.add(
                m.SnapshotCandidate(
                    session_id=owner_id,
                    snapshot_id=snapshot.id,
                    entity_id=entity.id,
                    entity_type="movie",
                    rank=index + 1,
                    affinity=1.0 - index * 0.05,
                )
            )
        db.flush()
        receipt = m.CurationReceipt(
            session_id=owner_id,
            game_id=game.id,
            curator_mode="fixture",
            seed_entity_id=seed.id,
            seed_type="artist",
            target_domains_considered=["movie"],
            target_domains_selected=["movie"],
            qloo_request_count=0,
            tool_request_count=0,
            model_request_count=0,
            candidate_count_received=10,
            rejection_counts={},
            valid_pair_count=5,
            bounded_correction_count=0,
            five_round_path_verified=True,
            provider_version=private_markers[1],
            validator_version=private_markers[2],
            elapsed_ms=1,
            status="succeeded",
        )
        db.add(receipt)
        pairs = []
        for index in range(5):
            pair = m.PrivatePair(
                id=uuid4(),
                session_id=owner_id,
                game_id=game.id,
                snapshot_id=snapshot.id,
                left_entity_id=contestants[index * 2 + 1].id,
                right_entity_id=contestants[index * 2].id,
                winner_entity_id=contestants[index * 2].id,
                difficulty="easy",
            )
            db.add(pair)
            pairs.append(pair)
        db.add(
            m.ProviderCache(
                session_id=owner_id,
                provider="fixture",
                key_hash=hashlib.sha256(b"private-cache").hexdigest(),
                payload={"raw": private_markers[3]},
                rights_policy="project_owned",
                expires_at=expiry,
            )
        )
        db.flush()
        round_, left, right = deliver(db, owner_id, game.id, pairs[0], 1)
        if answered:
            db.add(
                m.Answer(
                    session_id=owner_id,
                    game_id=game.id,
                    round_id=round_.id,
                    choice_id=left.id,
                    idempotency_key="synthetic-security-first-answer",
                    correct=True,
                )
            )
            db.flush()
        return PrivateGraph(
            owner_id,
            game.id,
            snapshot.id,
            seed.id,
            pairs[0].id,
            round_.id,
            left.id,
            right.id,
            tuple(entity.id for entity in contestants[2:]),
            tuple(pair.id for pair in pairs[1:]),
            future_names,
            private_markers,
        )


def deliver(db: DbSession, owner_id: UUID, game_id: UUID, pair: m.PrivatePair, ordinal: int):
    round_ = m.DeliveredRound(
        id=uuid4(), session_id=owner_id, game_id=game_id, pair_id=pair.id, ordinal=ordinal
    )
    db.add(round_)
    db.flush()
    left = m.RoundContestant(
        id=uuid4(),
        session_id=owner_id,
        game_id=game_id,
        round_id=round_.id,
        entity_id=pair.left_entity_id,
        side="left",
    )
    right = m.RoundContestant(
        id=uuid4(),
        session_id=owner_id,
        game_id=game_id,
        round_id=round_.id,
        entity_id=pair.right_entity_id,
        side="right",
    )
    db.add_all([left, right])
    db.flush()
    return round_, left, right
