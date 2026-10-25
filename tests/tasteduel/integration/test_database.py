"""Real PostgreSQL enforcement, using synthetic owned graphs only."""

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from tasteduel.persistence import models as m
from tasteduel.persistence.db import scoped_session
from tests.tasteduel.security._seed import deliver, seed_private_graph


def make_owner(engine):
    owner = uuid4()
    with scoped_session(engine, owner) as db:
        db.add(
            m.Session(
                id=owner,
                token_hash=hashlib.sha256(owner.bytes).hexdigest(),
                expires_at=datetime.now(UTC) + timedelta(hours=2),
            )
        )
    return owner


def graph(engine, *, answered=False):
    owner = make_owner(engine)
    return seed_private_graph(engine, owner, answered=answered)


def prepare_pair(engine):
    """A minimal not-yet-delivered graph for testing the precise insertion guards."""
    owner = make_owner(engine)
    expiry = datetime.now(UTC) + timedelta(minutes=30)
    ids = [uuid4() for _ in range(3)]
    game_id, snapshot_id, pair_id = uuid4(), uuid4(), uuid4()
    with scoped_session(engine, owner) as db:
        for index, entity_id in enumerate(ids):
            db.add(
                m.Entity(
                    id=entity_id,
                    session_id=owner,
                    entity_type="artist",
                    name=f"Synthetic artist {index}",
                    provider="fixture",
                    provider_entity_id=str(index),
                    attribution="Project-owned test data",
                    rights_policy="synthetic-test-only",
                    expires_at=expiry,
                )
            )
        db.flush()
        db.add(
            m.Game(
                id=game_id,
                session_id=owner,
                seed_entity_id=ids[0],
                seed_type="artist",
                scoring_version="synthetic-score-v1",
                validator_version="synthetic-validator-v1",
                expires_at=expiry,
            )
        )
        db.flush()
        db.add(
            m.RankingSnapshot(
                id=snapshot_id,
                session_id=owner,
                game_id=game_id,
                target_type="artist",
                query_context_hash="a" * 64,
                provider_version="fixture-v1",
                score_semantics="Synthetic descending",
                attribution="Project-owned test data",
                rights_policy="synthetic-test-only",
                expires_at=expiry,
            )
        )
        db.flush()
        db.add_all(
            [
                m.SnapshotCandidate(
                    session_id=owner,
                    snapshot_id=snapshot_id,
                    entity_id=entity_id,
                    entity_type="artist",
                    rank=index,
                    affinity=1.0 / index,
                )
                for index, entity_id in enumerate(ids[1:], 1)
            ]
        )
        db.flush()
        db.add(
            m.PrivatePair(
                id=pair_id,
                session_id=owner,
                game_id=game_id,
                snapshot_id=snapshot_id,
                left_entity_id=ids[1],
                right_entity_id=ids[2],
                winner_entity_id=ids[1],
                difficulty="easy",
            )
        )
    return owner, game_id, snapshot_id, pair_id, ids


def complete_game(engine):
    seeded = graph(engine, answered=True)
    with scoped_session(engine, seeded.owner_id) as db:
        for ordinal, pair_id in enumerate(seeded.future_pair_ids, 2):
            pair = db.get(m.PrivatePair, pair_id)
            round_, _, right = deliver(db, seeded.owner_id, seeded.game_id, pair, ordinal)
            db.add(
                m.Answer(
                    session_id=seeded.owner_id,
                    game_id=seeded.game_id,
                    round_id=round_.id,
                    choice_id=right.id,
                    idempotency_key=f"answer-{ordinal}",
                    correct=False,
                )
            )
            db.flush()
        db.add(
            m.GameResult(
                session_id=seeded.owner_id,
                game_id=seeded.game_id,
                score=4,
                scoring_version="synthetic-score-v1",
            )
        )
    return seeded


def test_answer_derives_correctness_and_advances_revision_only_after_insert(db_owner_engine):
    seeded = graph(db_owner_engine, answered=True)
    with scoped_session(db_owner_engine, seeded.owner_id) as db:
        answer = db.scalar(select(m.Answer).where(m.Answer.round_id == seeded.first_round_id))
        game = db.get(m.Game, seeded.game_id)
        assert answer.correct is False  # Caller supplied True for the losing left side.
        assert (game.current_ordinal, game.revision, game.status) == (1, 2, "playing")
    with pytest.raises(DBAPIError), scoped_session(db_owner_engine, seeded.owner_id) as db:
        db.add(
            m.Answer(
                session_id=seeded.owner_id,
                game_id=seeded.game_id,
                round_id=seeded.first_round_id,
                choice_id=seeded.first_right_choice_id,
                idempotency_key="contradictory-second-answer",
                correct=True,
            )
        )
        db.flush()
    with scoped_session(db_owner_engine, seeded.owner_id) as db:
        assert db.get(m.Game, seeded.game_id).revision == 2


def test_next_round_requires_prior_answer_and_two_committed_contestants(db_owner_engine):
    seeded = graph(db_owner_engine)
    with pytest.raises(DBAPIError), scoped_session(db_owner_engine, seeded.owner_id) as db:
        pair = db.get(m.PrivatePair, seeded.future_pair_ids[0])
        deliver(db, seeded.owner_id, seeded.game_id, pair, 2)
    with scoped_session(db_owner_engine, seeded.owner_id) as db:
        db.add(
            m.Answer(
                session_id=seeded.owner_id,
                game_id=seeded.game_id,
                round_id=seeded.first_round_id,
                choice_id=seeded.first_right_choice_id,
                idempotency_key="first",
                correct=False,
            )
        )
    with pytest.raises(DBAPIError), scoped_session(db_owner_engine, seeded.owner_id) as db:
        db.add(
            m.DeliveredRound(
                session_id=seeded.owner_id,
                game_id=seeded.game_id,
                pair_id=seeded.future_pair_ids[0],
                ordinal=2,
            )
        )
        db.flush()  # Flush succeeds; commit must reject the incomplete two-choice delivery.
    with scoped_session(db_owner_engine, seeded.owner_id) as db:
        assert db.get(m.Game, seeded.game_id).current_ordinal == 1


def test_pair_cannot_reverse_winner_and_result_requires_five_answers(db_owner_engine):
    owner, game_id, snapshot_id, pair_id, _ = prepare_pair(db_owner_engine)
    with pytest.raises(DBAPIError, match="strict consistent"), scoped_session(db_owner_engine, owner) as db:
        pair = db.get(m.PrivatePair, pair_id)
        db.add(
            m.PrivatePair(
                session_id=owner,
                game_id=game_id,
                snapshot_id=snapshot_id,
                left_entity_id=pair.left_entity_id,
                right_entity_id=pair.right_entity_id,
                winner_entity_id=pair.right_entity_id,
                difficulty="easy",
            )
        )
        db.flush()
    seeded = graph(db_owner_engine)
    with pytest.raises(DBAPIError), scoped_session(db_owner_engine, seeded.owner_id) as db:
        db.add(
            m.GameResult(
                session_id=seeded.owner_id,
                game_id=seeded.game_id,
                score=5,
                scoring_version="synthetic-score-v1",
            )
        )
        db.flush()


def test_no_repeat_entities_even_in_different_pairs(db_owner_engine):
    owner, game_id, _, pair_id, _ = prepare_pair(db_owner_engine)
    second_pair_id = uuid4()
    with scoped_session(db_owner_engine, owner) as db:
        pair = db.get(m.PrivatePair, pair_id)
        db.add(
            m.PrivatePair(
                id=second_pair_id,
                session_id=owner,
                game_id=game_id,
                snapshot_id=pair.snapshot_id,
                left_entity_id=pair.right_entity_id,
                right_entity_id=pair.left_entity_id,
                winner_entity_id=pair.left_entity_id,
                difficulty="easy",
            )
        )
        db.flush()
        first, left, _ = deliver(db, owner, game_id, pair, 1)
        db.add(
            m.Answer(
                session_id=owner,
                game_id=game_id,
                round_id=first.id,
                choice_id=left.id,
                idempotency_key="first",
                correct=False,
            )
        )
    with (
        pytest.raises(DBAPIError, match="uq_round_contestants_game_id_entity_id"),
        scoped_session(db_owner_engine, owner) as db,
    ):
        deliver(db, owner, game_id, db.get(m.PrivatePair, second_pair_id), 2)


def test_seed_cannot_be_a_candidate_and_pool_freezes_at_delivery(db_owner_engine):
    owner, game_id, snapshot_id, pair_id, ids = prepare_pair(db_owner_engine)
    with pytest.raises(DBAPIError, match="seed cannot compete"), scoped_session(db_owner_engine, owner) as db:
        db.add(
            m.SnapshotCandidate(
                session_id=owner,
                snapshot_id=snapshot_id,
                entity_id=ids[0],
                entity_type="artist",
                rank=3,
                affinity=0.1,
            )
        )
        db.flush()
    with scoped_session(db_owner_engine, owner) as db:
        deliver(db, owner, game_id, db.get(m.PrivatePair, pair_id), 1)
    with (
        pytest.raises(DBAPIError, match="frozen after first delivery"),
        scoped_session(db_owner_engine, owner) as db,
    ):
        pair = db.get(m.PrivatePair, pair_id)
        db.add(
            m.PrivatePair(
                session_id=owner,
                game_id=game_id,
                snapshot_id=snapshot_id,
                left_entity_id=pair.left_entity_id,
                right_entity_id=pair.right_entity_id,
                winner_entity_id=pair.winner_entity_id,
                difficulty="easy",
            )
        )
        db.flush()


def test_challenge_freezes_five_rounds_and_caps_expiry(db_owner_engine):
    seeded = complete_game(db_owner_engine)
    with scoped_session(db_owner_engine, seeded.owner_id) as db:
        game = db.get(m.Game, seeded.game_id)
        assert game.status == "completed"
        challenge = m.Challenge(
            id=uuid4(),
            session_id=seeded.owner_id,
            source_game_id=seeded.game_id,
            slug_hash=hashlib.sha256(uuid4().bytes).hexdigest(),
            creator_score=4,
            scoring_version=game.scoring_version,
            validator_version=game.validator_version,
            expires_at=game.expires_at,
        )
        db.add(challenge)
        db.flush()
        challenge_id = challenge.id
        rows = list(db.scalars(select(m.ChallengeRound).where(m.ChallengeRound.challenge_id == challenge_id)))
        assert sorted(row.ordinal for row in rows) == [1, 2, 3, 4, 5]
        assert len({row.winner_entity_id for row in rows}) == 5
    with pytest.raises(DBAPIError), scoped_session(db_owner_engine, seeded.owner_id) as db:
        db.execute(
            text("UPDATE tasteduel.challenges SET expires_at=expires_at+interval '1 day' WHERE id=:id"),
            {"id": challenge_id},
        )
    with pytest.raises(DBAPIError), scoped_session(db_owner_engine, seeded.owner_id) as db:
        db.execute(
            text(
                "UPDATE tasteduel.challenge_rounds SET winner_entity_id=left_entity_id WHERE challenge_id=:id"
            ),
            {"id": challenge_id},
        )


@pytest.mark.parametrize(
    "counts", [{"raw_provider_payload": 1}, {"missing_score": 11}, {"score_tie": -1}, {"score_tie": 1.5}]
)
def test_private_receipt_has_strict_rejection_shape(db_owner_engine, counts):
    # Evaluate the actual DB check helper, not a Python implementation mirror.
    with db_owner_engine.connect() as db:
        import json

        assert (
            db.scalar(
                text("SELECT tasteduel.valid_rejections(CAST(:counts AS jsonb),10)"),
                {"counts": json.dumps(counts)},
            )
            is False
        )


def test_composite_owner_fk_and_forced_rls(db_owner_engine, db_engine):
    first = graph(db_owner_engine)
    second = make_owner(db_owner_engine)
    with scoped_session(db_engine, second) as db:
        assert db.get(m.Game, first.game_id) is None
        assert db.scalar(select(m.CurationReceipt).where(m.CurationReceipt.game_id == first.game_id)) is None
    with pytest.raises(DBAPIError), scoped_session(db_engine, second) as db:
        db.add(m.Discovery(session_id=second, entity_id=first.seed_id))
        db.flush()


def test_mutation_signature_unique_and_completed_typed_outcome_immutable(db_owner_engine, db_engine):
    seeded = graph(db_owner_engine, answered=True)
    receipt_id = uuid4()
    with scoped_session(db_engine, seeded.owner_id) as db:
        game = db.get(m.Game, seeded.game_id)
        db.add(
            m.MutationReceipt(
                id=receipt_id,
                session_id=seeded.owner_id,
                operation="answer",
                idempotency_key="stable-answer-key",
                signature_hash="a" * 64,
                subject_kind="game",
                subject_id=game.id,
                expires_at=game.expires_at,
            )
        )
    with (
        pytest.raises(DBAPIError, match="uq_mutation_receipts_session_id_operation_idempotency_key"),
        scoped_session(db_engine, seeded.owner_id) as db,
    ):
        db.add(
            m.MutationReceipt(
                session_id=seeded.owner_id,
                operation="answer",
                idempotency_key="stable-answer-key",
                signature_hash="b" * 64,
                subject_kind="game",
                subject_id=seeded.game_id,
                expires_at=db.get(m.Game, seeded.game_id).expires_at,
            )
        )
        db.flush()
    with scoped_session(db_engine, seeded.owner_id) as db:
        receipt = db.get(m.MutationReceipt, receipt_id)
        assert receipt.signature_hash == "a" * 64
        receipt.status = "completed"
        receipt.outcome_kind = "round"
        receipt.outcome_id = seeded.first_round_id
        receipt.outcome_revision = 2
    with (
        pytest.raises(DBAPIError, match="completed outcome are immutable"),
        scoped_session(db_engine, seeded.owner_id) as db,
    ):
        db.execute(
            text("UPDATE tasteduel.mutation_receipts SET outcome_revision=3 WHERE id=:id"), {"id": receipt_id}
        )


def test_mutation_receipt_cannot_reference_another_owners_subject_or_outcome(db_owner_engine, db_engine):
    first = graph(db_owner_engine, answered=True)
    second = graph(db_owner_engine, answered=True)
    with scoped_session(db_engine, second.owner_id) as db:
        expiry = db.get(m.Game, second.game_id).expires_at
    with (
        pytest.raises(DBAPIError, match="subject must belong"),
        scoped_session(db_engine, second.owner_id) as db,
    ):
        db.add(
            m.MutationReceipt(
                session_id=second.owner_id,
                operation="answer",
                idempotency_key="cross-owner-subject",
                signature_hash="a" * 64,
                subject_kind="game",
                subject_id=first.game_id,
                expires_at=expiry,
            )
        )
        db.flush()

    with (
        pytest.raises(DBAPIError, match="typed owned subject result"),
        scoped_session(db_engine, second.owner_id) as db,
    ):
        db.add(
            m.MutationReceipt(
                session_id=second.owner_id,
                operation="answer",
                idempotency_key="cross-owner-outcome",
                signature_hash="a" * 64,
                subject_kind="game",
                subject_id=second.game_id,
                expires_at=expiry,
                status="completed",
                outcome_kind="round",
                outcome_id=first.first_round_id,
            )
        )
        db.flush()


@pytest.mark.parametrize(
    "answered,revision,message",
    [
        (False, 1, "requires an accepted answer"),
        (True, 999, "authoritative game revision"),
        (True, 1, "authoritative game revision"),
    ],
)
def test_completed_answer_receipt_requires_accepted_answer_and_exact_revision(
    db_owner_engine, db_engine, answered, revision, message
):
    seeded = graph(db_owner_engine, answered=answered)
    with scoped_session(db_engine, seeded.owner_id) as db:
        expiry = db.get(m.Game, seeded.game_id).expires_at
    with pytest.raises(DBAPIError, match=message), scoped_session(db_engine, seeded.owner_id) as db:
        db.add(
            m.MutationReceipt(
                session_id=seeded.owner_id,
                operation="answer",
                idempotency_key="invalid-completion",
                signature_hash="a" * 64,
                subject_kind="game",
                subject_id=seeded.game_id,
                expires_at=expiry,
                status="completed",
                outcome_kind="round",
                outcome_id=seeded.first_round_id,
                outcome_revision=revision,
            )
        )
        db.flush()


def test_completed_receipt_keeps_accepted_revision_after_later_advancement(db_owner_engine, db_engine):
    seeded = graph(db_owner_engine, answered=True)
    receipt_id = uuid4()
    with scoped_session(db_engine, seeded.owner_id) as db:
        db.add(
            m.MutationReceipt(
                id=receipt_id,
                session_id=seeded.owner_id,
                operation="answer",
                idempotency_key="stable-completion",
                signature_hash="a" * 64,
                subject_kind="game",
                subject_id=seeded.game_id,
                expires_at=db.get(m.Game, seeded.game_id).expires_at,
                status="completed",
                outcome_kind="round",
                outcome_id=seeded.first_round_id,
                outcome_revision=2,
            )
        )
    with scoped_session(db_owner_engine, seeded.owner_id) as db:
        deliver(db, seeded.owner_id, seeded.game_id, db.get(m.PrivatePair, seeded.future_pair_ids[0]), 2)
    with scoped_session(db_engine, seeded.owner_id) as db:
        assert db.get(m.Game, seeded.game_id).revision == 3
        assert db.get(m.MutationReceipt, receipt_id).outcome_revision == 2
