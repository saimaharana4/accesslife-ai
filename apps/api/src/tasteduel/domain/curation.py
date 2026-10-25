"""Private execution facts. Never use this model as a public response schema."""

from typing import Annotated
from uuid import UUID

from pydantic import Field, StrictBool, model_validator

from .types import (
    Count,
    CuratorMode,
    EntityType,
    GenerationStatus,
    RejectionReason,
    StrictRecord,
    UtcDatetime,
    VersionToken,
)


class CurationReceipt(StrictRecord):
    game_id: UUID
    curator_mode: CuratorMode
    seed_entity_id: UUID
    seed_type: EntityType
    target_domains_considered: Annotated[tuple[EntityType, ...], Field(min_length=1, max_length=2)]
    target_domains_selected: Annotated[tuple[EntityType, ...], Field(max_length=2)]
    qloo_request_count: Annotated[Count, Field(le=6)]
    tool_request_count: Annotated[Count, Field(le=24)]
    model_request_count: Annotated[Count, Field(le=4)]
    candidate_count_received: Count
    # One deterministic primary rejection per candidate, not overlapping checks.
    rejection_counts: dict[RejectionReason, Count]
    valid_pair_count: Annotated[Count, Field(le=200)]
    bounded_correction_count: Annotated[Count, Field(le=1)]
    five_round_path_verified: StrictBool
    provider_version: VersionToken
    harness_version: VersionToken | None = None
    model_version: VersionToken | None = None
    validator_version: VersionToken
    elapsed_ms: Annotated[Count, Field(le=120_000)]
    status: GenerationStatus
    created_at: UtcDatetime

    @model_validator(mode="after")
    def consistent_execution(self):
        considered = set(self.target_domains_considered)
        selected = set(self.target_domains_selected)
        if len(considered) != len(self.target_domains_considered) or len(selected) != len(
            self.target_domains_selected
        ):
            raise ValueError("Target domains must be unique")
        if not selected.issubset(considered):
            raise ValueError("Selected domains were not considered")
        if sum(self.rejection_counts.values()) > self.candidate_count_received:
            raise ValueError("Primary rejection counts exceed candidates received")
        if self.curator_mode == CuratorMode.FIXTURE and (self.qloo_request_count or self.model_request_count):
            raise ValueError("Fixture curation cannot claim Qloo/model calls")
        if self.curator_mode == CuratorMode.DETERMINISTIC_QLOO and self.model_request_count:
            raise ValueError("Deterministic curation cannot claim model execution")
        if self.status == GenerationStatus.SUCCEEDED:
            if not selected or not self.five_round_path_verified or self.valid_pair_count < 5:
                raise ValueError("Successful generation requires a validated five-round path")
            if self.candidate_count_received < 10:
                raise ValueError("Five nonrepeating rounds require at least ten candidates")
            if self.curator_mode != CuratorMode.FIXTURE and not self.qloo_request_count:
                raise ValueError("Successful Qloo curation requires an actual Qloo request")
            if self.curator_mode == CuratorMode.GENUINE_AGENT and (
                not self.model_request_count or not self.model_version
            ):
                raise ValueError("Genuine agent execution requires a model call and version")
        return self
