"""Adversarial contract checks independent of the DTO author's happy paths."""

import pytest
from pydantic import ValidationError

from tasteduel.api import schemas
from tasteduel.domain.curation import CurationReceipt


PUBLIC_BOUNDARIES = (
    "ArtworkPublic",
    "EntityPublic",
    "ChoicePublic",
    "PlayableRoundPublic",
    "RevealedRoundPublic",
    "GamePublic",
    "GameResultPublic",
    "ChallengeInvitationPublic",
    "CurationSummaryPublic",
    "RevealedEvidencePublic",
)
PRIVATE_FIELDS = (
    "raw_provider_payload",
    "chain_of_thought",
    "future_answer_keys",
    "private_pool",
    "curation_receipt",
)


@pytest.mark.parametrize("boundary", PUBLIC_BOUNDARIES)
@pytest.mark.parametrize("field", PRIVATE_FIELDS)
def test_public_contract_explicitly_rejects_private_payload_fields(boundary, field):
    model = getattr(schemas, boundary)
    with pytest.raises(ValidationError) as failure:
        model.model_validate({field: {"synthetic_private": "DO_NOT_SERIALIZE"}})
    # Missing required fields alone must not make this test pass: the malicious
    # field itself has to be rejected, rather than ignored or copied wholesale.
    assert any(
        error["type"] == "extra_forbidden" and error["loc"] == (field,) for error in failure.value.errors()
    )


@pytest.mark.parametrize("boundary", PUBLIC_BOUNDARIES)
def test_private_records_cannot_be_implicitly_converted_to_public_dtos(boundary):
    accessed = []

    class PrivateRecord:
        def __getattr__(self, name):
            accessed.append(name)
            return "PRIVATE_RECORD_ATTRIBUTE"

    with pytest.raises(ValidationError) as failure:
        getattr(schemas, boundary).model_validate(PrivateRecord())
    assert any(error["type"] == "model_type" for error in failure.value.errors())
    # Pydantic may inspect its own protocol marker; public fields must never be
    # pulled from arbitrary persistence/domain objects by from_attributes.
    public_fields = set(getattr(schemas, boundary).model_fields)
    assert not public_fields.intersection(accessed)


@pytest.mark.parametrize("field", PRIVATE_FIELDS[:-1])
def test_private_receipt_is_structured_facts_not_a_raw_reasoning_container(field):
    with pytest.raises(ValidationError) as failure:
        CurationReceipt.model_validate({field: "SYNTHETIC_RAW_REASONING_MARKER"})
    assert any(
        error["type"] == "extra_forbidden" and error["loc"] == (field,) for error in failure.value.errors()
    )


@pytest.mark.parametrize("field", ["choices", "answered_rounds", "winning_choice_id", "creator_session_id"])
def test_challenge_invitation_is_not_a_round_or_creator_identity_transport(field):
    with pytest.raises(ValidationError) as failure:
        schemas.ChallengeInvitationPublic.model_validate({field: "SYNTHETIC_PRIVATE_INVITATION_MARKER"})
    assert any(
        error["type"] == "extra_forbidden" and error["loc"] == (field,) for error in failure.value.errors()
    )
