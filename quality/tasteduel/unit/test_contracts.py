"""Synthetic contract checks; no database, external provider or model calls."""

import json
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID

import pytest
from pydantic import ValidationError

from tasteduel.api.schemas import (
    AnswerRequest,
    ChallengeInvitationPublic,
    CurationSummaryPublic,
    ErrorEnvelope,
    GamePublic,
    GameResultPublic,
    PlayableRoundPublic,
    RevealedEvidencePublic,
    RevealedRoundPublic,
    SessionCreateRequest,
    SessionPublic,
)
from tasteduel.domain.curation import CurationReceipt

NOW = datetime(2026, 10, 25, 8, tzinfo=UTC)


def entity(number=1, kind="artist"):
    return {"id": UUID(int=number), "name": f"Synthetic entity {number}", "type": kind, "source": "fixture"}


def playable(ordinal=1):
    return {
        "state": "unanswered",
        "game_id": UUID(int=20),
        "round_id": UUID(int=100 + ordinal),
        "ordinal": ordinal,
        "revision": ordinal * 2,
        "seed": entity(),
        "target_type": "movie",
        "question": "Which fictional film ranks higher?",
        "source": "fixture",
        "choices": (
            {"id": UUID(int=400 + ordinal * 2), "entity": entity(200 + ordinal * 2, "movie")},
            {"id": UUID(int=401 + ordinal * 2), "entity": entity(201 + ordinal * 2, "movie")},
        ),
    }


def receipt(**changes):
    data = {
        "game_id": UUID(int=20),
        "curator_mode": "fixture",
        "seed_entity_id": UUID(int=1),
        "seed_type": "artist",
        "target_domains_considered": ("movie", "artist"),
        "target_domains_selected": ("movie",),
        "qloo_request_count": 0,
        "tool_request_count": 0,
        "model_request_count": 0,
        "candidate_count_received": 12,
        "rejection_counts": {"duplicate_entity": 1, "near_tie": 1},
        "valid_pair_count": 6,
        "bounded_correction_count": 0,
        "five_round_path_verified": True,
        "provider_version": "synthetic-v1",
        "harness_version": None,
        "model_version": None,
        "validator_version": "validator-v1",
        "elapsed_ms": 2400,
        "status": "succeeded",
        "created_at": NOW,
    }
    return data | changes


def summary(**changes):
    return {
        "curator_mode": "fixture",
        "source": "fixture",
        "target_domains": ("movie",),
        "candidate_count_received": 12,
        "rejection_counts": {"duplicate_entity": 1},
        "bounded_correction_count": 0,
        "five_round_path_verified": True,
    } | changes


def revealed(ordinal=1, correct=True, score=1):
    data = playable(ordinal)
    data.pop("question")
    choices = data["choices"]
    return data | {
        "state": "revealed",
        "selected_choice_id": choices[0]["id"],
        "winning_choice_id": choices[0 if correct else 1]["id"],
        "correct": correct,
        "cumulative_score": score,
        "accepted_at": NOW,
    }


@pytest.mark.parametrize(
    "field",
    [
        "winning_choice_id",
        "rank",
        "affinity",
        "private_pool",
        "curation_receipt",
        "future_rounds",
        "chain_of_thought",
    ],
)
def test_playable_rejects_private_fields_instead_of_silently_filtering(field):
    with pytest.raises(ValidationError):
        PlayableRoundPublic.model_validate(playable() | {field: "private-marker"})


def test_playable_nested_allowlists_and_no_orm_auto_serialization():
    data = playable()
    data["choices"][0]["entity"]["rank"] = 1
    with pytest.raises(ValidationError):
        PlayableRoundPublic.model_validate(data)
    with pytest.raises(ValidationError):
        PlayableRoundPublic.model_validate(SimpleNamespace(**playable()))
    public = PlayableRoundPublic.model_validate(playable()).model_dump(mode="json")
    assert public["state"] == "unanswered"
    assert len(public["choices"]) == 2
    serialized = json.dumps(public)
    assert not any(
        token in serialized
        for token in ('"winner"', '"rank"', '"affinity"', '"receipt"', '"future"', "private-marker")
    )
    assert "CurationReceipt" not in json.dumps(PlayableRoundPublic.model_json_schema())


def test_session_never_accepts_token_and_requests_require_revision_uuid_and_strict_integer():
    with pytest.raises(ValidationError):
        SessionCreateRequest.model_validate({"token": "private"})
    with pytest.raises(ValidationError):
        SessionPublic(active=True, expires_at=NOW, token="private")
    valid = {"round_id": str(UUID(int=1)), "choice_id": str(UUID(int=2)), "expected_revision": 2}
    assert AnswerRequest.model_validate(valid).round_id == UUID(int=1)
    for patch in (
        {"expected_revision": True},
        {"expected_revision": -1},
        {"round_id": "not-a-uuid"},
        {"correct": True},
    ):
        with pytest.raises(ValidationError):
            AnswerRequest.model_validate(valid | patch)


@pytest.mark.parametrize(
    "field",
    [
        "reasoning",
        "chain_of_thought",
        "prompt",
        "raw_response",
        "unused_future_answer_keys",
        "provider_payload",
    ],
)
def test_receipt_never_accepts_unrestricted_execution_payloads(field):
    with pytest.raises(ValidationError):
        CurationReceipt.model_validate(receipt(**{field: {"private": "marker"}}))


@pytest.mark.parametrize(
    "patch",
    [
        {"target_domains_selected": ("artist",), "target_domains_considered": ("movie",)},
        {"rejection_counts": {"free_form_reasoning": 1}},
        {"rejection_counts": {"near_tie": 13}},
        {"qloo_request_count": 1},
        {"model_request_count": 1},
        {"five_round_path_verified": False},
        {"five_round_path_verified": 1},
        {"valid_pair_count": 4},
        {"elapsed_ms": -1},
        {"curator_mode": "genuine_agent", "qloo_request_count": 1},
    ],
)
def test_receipt_rejects_false_provenance_or_invalid_execution_facts(patch):
    with pytest.raises(ValidationError):
        CurationReceipt.model_validate(receipt(**patch))


def test_receipt_utc_and_failed_attempts_are_structured_not_public_summaries():
    local = NOW.astimezone(timezone(timedelta(hours=5, minutes=30)))
    private = CurationReceipt.model_validate(receipt(created_at=local))
    assert private.created_at == NOW and private.created_at.tzinfo == UTC
    assert private.elapsed_ms == 2400
    with pytest.raises(ValidationError):
        CurationReceipt.model_validate(receipt(created_at=NOW.replace(tzinfo=None)))
    failed = CurationReceipt.model_validate(
        receipt(
            status="failed", five_round_path_verified=False, valid_pair_count=0, target_domains_selected=()
        )
    )
    assert failed.status == "failed"
    with pytest.raises(ValidationError):
        CurationSummaryPublic.model_validate(private)
    with pytest.raises(ValidationError):
        CurationSummaryPublic.model_validate(private.model_dump())


@pytest.mark.parametrize(
    "field",
    [
        "game_id",
        "seed_entity_id",
        "model_version",
        "raw_response",
        "chain_of_thought",
        "future_rounds",
        "winning_choice_id",
        "valid_pair_count",
    ],
)
def test_public_summary_excludes_private_and_future_pair_facts(field):
    with pytest.raises(ValidationError):
        CurationSummaryPublic.model_validate(summary(**{field: "private-marker"}))


def test_summary_success_and_provenance_are_not_guessed():
    assert CurationSummaryPublic.model_validate(summary()).source == "fixture"
    for patch in (
        {"source": "qloo"},
        {"five_round_path_verified": False},
        {"candidate_count_received": 9},
        {"status": "failed"},
    ):
        with pytest.raises(ValidationError):
            CurationSummaryPublic.model_validate(summary(**patch))


def test_reveal_optional_evidence_is_factual_typed_and_current_context_only():
    evidence = {
        "source": "fixture",
        "context": {"seed": entity(), "target_type": "movie", "retrieved_at": NOW},
        "supported_explanation": {
            "kind": "synthetic",
            "text": "Invented fixture ordering only.",
            "attribution": "Synthetic fixture",
        },
    }
    value = RevealedRoundPublic.model_validate(
        revealed() | {"evidence": evidence, "curation_summary": summary()}
    )
    assert value.evidence.source == "fixture" and value.curation_summary.five_round_path_verified
    for patch in ({"raw_response": {}}, {"future_choices": []}, {"chain_of_thought": "private"}):
        with pytest.raises(ValidationError):
            RevealedEvidencePublic.model_validate(evidence | patch)
    with pytest.raises(ValidationError):
        RevealedEvidencePublic.model_validate(
            evidence
            | {
                "supported_explanation": {
                    "kind": "provider_returned",
                    "text": "Invented",
                    "attribution": "Qloo",
                }
            }
        )
    with pytest.raises(ValidationError):
        RevealedRoundPublic.model_validate(revealed() | {"winning_choice_id": UUID(int=999)})


def test_discriminated_game_state_serializes_only_its_actual_current_round():
    game = {
        "game_id": UUID(int=20),
        "phase": "playing",
        "mode": "solo",
        "revision": 2,
        "seed": entity(),
        "curator_mode": "fixture",
        "source": "fixture",
        "current_ordinal": 1,
        "answered_count": 0,
        "score": 0,
        "expires_at": NOW + timedelta(hours=1),
        "current_round": playable(),
    }
    value = GamePublic.model_validate(game).model_dump(mode="json")
    assert value["current_round"]["state"] == "unanswered"
    assert "winning_choice_id" not in json.dumps(value)
    game |= {"answered_count": 1, "score": 1, "current_round": revealed()}
    assert GamePublic.model_validate(game).current_round.state == "revealed"
    with pytest.raises(ValidationError):
        GamePublic.model_validate(game | {"answered_count": 0})


def test_result_requires_ordered_five_distinct_rounds_and_actual_cumulative_scores():
    answers = tuple(revealed(n, correct=n % 2 == 1, score=(n + 1) // 2) for n in range(1, 6))
    result = {
        "game_id": UUID(int=20),
        "score": 3,
        "source": "fixture",
        "curator_mode": "fixture",
        "answered_rounds": answers,
        "expires_at": NOW,
    }
    assert GameResultPublic.model_validate(result).score == 3
    for patch in (
        {"score": 4},
        {"answered_rounds": answers[:4]},
        {"answered_rounds": tuple(reversed(answers))},
    ):
        with pytest.raises(ValidationError):
            GameResultPublic.model_validate(result | patch)


def test_public_invitation_and_errors_cannot_smuggle_private_payloads():
    invitation = {
        "slug": "synthetic-challenge-slug-123",
        "seed": entity(),
        "creator_score": 3,
        "source": "fixture",
        "expires_at": NOW,
    }
    assert ChallengeInvitationPublic.model_validate(invitation).total == 5
    for field in ("creator_session_id", "rounds", "answer_key", "future_choices"):
        with pytest.raises(ValidationError):
            ChallengeInvitationPublic.model_validate(invitation | {field: "private"})
    error = {
        "code": "INVALID_INPUT",
        "message": "Check the request fields.",
        "retryable": False,
        "request_id": UUID(int=10),
        "field_errors": ({"loc": ("body", "round_id"), "type": "invalid"},),
    }
    assert ErrorEnvelope.model_validate({"error": error}).error.code == "INVALID_INPUT"
    for patch in ({"input": "private"}, {"ctx": {"secret": "private"}}, {"traceback": "private"}):
        with pytest.raises(ValidationError):
            ErrorEnvelope.model_validate({"error": error | patch})
