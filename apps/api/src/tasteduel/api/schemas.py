"""Allowlisted browser contracts, independent from private persistence models.

No ORM auto-serialization or private CurationReceipt type is imported here.
Application projections must enforce ownership and answer state before creating
reveals; shape validation alone does not establish authorization.
"""

from typing import Annotated, Literal
from uuid import UUID

import unicodedata

from pydantic import Field, StrictBool, StrictInt, StringConstraints, field_validator, model_validator

from tasteduel.domain.types import (
    Count,
    CuratorMode,
    EntityType,
    GameMode,
    GamePhase,
    Ordinal,
    RankingSource,
    RejectionReason,
    Revision,
    Score,
    ShortText,
    StrictRecord,
    UtcDatetime,
    validate_provenance,
)

Message = Annotated[str, StringConstraints(min_length=1, max_length=600)]


Nickname = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=24)]


class SessionNameRequest(StrictRecord):
    display_name: Nickname

    @field_validator("display_name", mode="before")
    @classmethod
    def clean_name(cls, value):
        if not isinstance(value, str):
            raise ValueError("A nickname is required")
        value = unicodedata.normalize("NFKC", value).strip()
        if any(unicodedata.category(c).startswith("C") or c in "<>" for c in value):
            raise ValueError("Use a nickname without markup or control characters")
        return " ".join(value.split())


class SessionCreateRequest(StrictRecord):
    # Optional for existing API clients. New onboarding always submits a name.
    display_name: Nickname | None = None

    @field_validator("display_name", mode="before")
    @classmethod
    def optional_name(cls, value):
        return None if value is None else SessionNameRequest.clean_name(value)


class SessionPublic(StrictRecord):
    active: StrictBool
    expires_at: UtcDatetime
    display_name: Nickname | None = None
    resumable_game_ids: Annotated[tuple[UUID, ...], Field(max_length=20)] = ()


class ArtworkPublic(StrictRecord):
    kind: Literal["owned_fallback", "licensed"]
    # A reviewed asset registry ID, never an arbitrary provider/image URL.
    asset_id: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")]
    attribution: ShortText | None = None


class EntityPublic(StrictRecord):
    id: UUID
    name: ShortText
    type: EntityType
    source: RankingSource
    artwork: ArtworkPublic | None = None
    disambiguation: ShortText | None = None


class EntitySearchPublic(StrictRecord):
    status: Literal["ok", "empty", "needs_input", "partial", "unavailable"]
    results: Annotated[tuple[EntityPublic, ...], Field(max_length=20)] = ()
    message: Message | None = None


class ChoicePublic(StrictRecord):
    """An opaque delivered choice, distinct from its searchable entity ID."""

    id: UUID
    entity: EntityPublic


class CreateGameRequest(StrictRecord):
    seed_entity_id: UUID
    seed_type: EntityType
    mode: Literal["solo"] = "solo"


class AnswerRequest(StrictRecord):
    round_id: UUID
    choice_id: UUID
    expected_revision: Revision


class AdvanceRequest(StrictRecord):
    answered_round_id: UUID
    expected_revision: Revision


class DiscoveryCreateRequest(StrictRecord):
    entity_id: UUID


class ChallengeCreateRequest(StrictRecord):
    game_id: UUID


class ChallengePlayRequest(StrictRecord):
    new_attempt: StrictBool = False


class CurationSummaryPublic(StrictRecord):
    status: Literal["succeeded"] = "succeeded"
    curator_mode: CuratorMode
    source: RankingSource
    target_domains: Annotated[tuple[EntityType, ...], Field(min_length=1, max_length=2)]
    candidate_count_received: Count
    rejection_counts: dict[RejectionReason, Count]
    bounded_correction_count: Annotated[Count, Field(le=1)]
    five_round_path_verified: StrictBool

    @model_validator(mode="after")
    def safe_success_facts(self):
        validate_provenance(self.curator_mode, self.source)
        if not self.five_round_path_verified or self.candidate_count_received < 10:
            raise ValueError("Only successful five-round curation may be summarized")
        if len(set(self.target_domains)) != len(self.target_domains):
            raise ValueError("Target domains must be unique")
        if sum(self.rejection_counts.values()) > self.candidate_count_received:
            raise ValueError("Primary rejections exceed received candidates")
        return self


class SupportedExplanationPublic(StrictRecord):
    kind: Literal["provider_returned", "factual_template", "synthetic"]
    text: Message
    attribution: ShortText


class RankingContextPublic(StrictRecord):
    seed: EntityPublic
    target_type: EntityType
    retrieved_at: UtcDatetime


class RevealedEvidencePublic(StrictRecord):
    source: RankingSource
    context: RankingContextPublic
    supported_explanation: SupportedExplanationPublic | None = None

    @model_validator(mode="after")
    def explicit_source(self):
        if self.context.seed.source != self.source:
            raise ValueError("Evidence and seed provenance disagree")
        if self.supported_explanation:
            kind = self.supported_explanation.kind
            if self.source == RankingSource.FIXTURE and kind == "provider_returned":
                raise ValueError("Fixture evidence cannot claim a returned provider explanation")
            if self.source == RankingSource.QLOO and kind == "synthetic":
                raise ValueError("Qloo evidence cannot include synthetic explanations")
        return self


class PlayableRoundPublic(StrictRecord):
    state: Literal["unanswered"] = "unanswered"
    game_id: UUID
    round_id: UUID
    ordinal: Ordinal
    total: Literal[5] = 5
    revision: Revision
    seed: EntityPublic
    target_type: EntityType
    question: ShortText
    choices: tuple[ChoicePublic, ChoicePublic]
    source: RankingSource

    @model_validator(mode="after")
    def same_type_context(self):
        entities = {choice.entity.id for choice in self.choices}
        if self.choices[0].id == self.choices[1].id or len(entities) != 2 or self.seed.id in entities:
            raise ValueError("A round requires distinct contestants different from its seed")
        if any(
            choice.entity.type != self.target_type or choice.entity.source != self.source
            for choice in self.choices
        ):
            raise ValueError("Both choices must have the same target type and source")
        if self.seed.source != self.source:
            raise ValueError("Seed and ranking provenance disagree")
        return self


class RevealedRoundPublic(StrictRecord):
    state: Literal["revealed"] = "revealed"
    game_id: UUID
    round_id: UUID
    ordinal: Ordinal
    total: Literal[5] = 5
    revision: Revision
    seed: EntityPublic
    target_type: EntityType
    choices: tuple[ChoicePublic, ChoicePublic]
    selected_choice_id: UUID
    winning_choice_id: UUID
    correct: StrictBool
    cumulative_score: Score
    source: RankingSource
    accepted_at: UtcDatetime
    evidence: RevealedEvidencePublic | None = None
    curation_summary: CurationSummaryPublic | None = None

    @model_validator(mode="after")
    def accepted_round_only(self):
        ids = {choice.id for choice in self.choices}
        entities = {choice.entity.id for choice in self.choices}
        if (
            len(ids) != 2
            or len(entities) != 2
            or self.seed.id in entities
            or not {self.selected_choice_id, self.winning_choice_id}.issubset(ids)
        ):
            raise ValueError("Revealed selections must refer to this distinct pair")
        if self.correct != (self.selected_choice_id == self.winning_choice_id):
            raise ValueError("Correctness contradicts the selected and winning choices")
        if self.cumulative_score > self.ordinal:
            raise ValueError("Score exceeds accepted round count")
        if self.correct and self.cumulative_score == 0:
            raise ValueError("A correct accepted answer contributes one point")
        if any(
            choice.entity.type != self.target_type or choice.entity.source != self.source
            for choice in self.choices
        ):
            raise ValueError("Both choices must have the declared target type and source")
        if self.seed.source != self.source:
            raise ValueError("Seed and ranking provenance disagree")
        if self.evidence and (
            self.evidence.source != self.source
            or self.evidence.context.target_type != self.target_type
            or self.evidence.context.seed.id != self.seed.id
        ):
            raise ValueError("Evidence does not describe this round context")
        if self.curation_summary and self.curation_summary.source != self.source:
            raise ValueError("Curation summary and ranking provenance disagree")
        return self


CurrentRoundPublic = Annotated[PlayableRoundPublic | RevealedRoundPublic, Field(discriminator="state")]


class GamePublic(StrictRecord):
    game_id: UUID
    phase: GamePhase
    mode: GameMode
    revision: Revision
    seed: EntityPublic
    curator_mode: CuratorMode
    source: RankingSource
    total: Literal[5] = 5
    current_ordinal: Annotated[StrictInt, Field(ge=0, le=5)]
    answered_count: Score
    score: Score
    expires_at: UtcDatetime
    current_round: CurrentRoundPublic | None = None

    @model_validator(mode="after")
    def consistent_progress(self):
        validate_provenance(self.curator_mode, self.source)
        if self.seed.source != self.source or self.score > self.answered_count:
            raise ValueError("Game provenance or score is inconsistent")
        if self.phase == GamePhase.COMPLETED and self.answered_count != 5:
            raise ValueError("A completed game has five accepted answers")
        if self.current_round:
            current = self.current_round
            if (
                current.game_id != self.game_id
                or current.ordinal != self.current_ordinal
                or current.revision != self.revision
                or current.seed.id != self.seed.id
                or current.source != self.source
            ):
                raise ValueError("Current round does not belong to this game revision")
            expected = current.ordinal if current.state == "revealed" else current.ordinal - 1
            if self.answered_count != expected:
                raise ValueError("Current round state disagrees with answer count")
            if current.state == "revealed" and current.cumulative_score != self.score:
                raise ValueError("Current reveal score disagrees with game score")
        return self


class GameGenerationPendingPublic(StrictRecord):
    game_id: UUID
    status: Literal["generation_in_progress"] = "generation_in_progress"
    retry_after_seconds: Annotated[StrictInt, Field(ge=1, le=30)]
    lease_expires_at: UtcDatetime


class GenerationStatusPublic(StrictRecord):
    """Observation only. No pool diagnostics, execution history or answer clues."""

    game_id: UUID
    status: Literal["generation_in_progress", "retryable", "succeeded", "failed", "cancelled"]
    lease_expires_at: UtcDatetime | None = None
    retry_after_seconds: Annotated[StrictInt | None, Field(ge=1, le=30)] = None
    recovery_action: Literal["wait_then_retry", "retry_same_request", "read_game", "start_new_game"]


class DiscoveryPublic(StrictRecord):
    entity: EntityPublic
    saved_at: UtcDatetime
    expires_at: UtcDatetime


class DiscoveriesPublic(StrictRecord):
    discoveries: Annotated[tuple[DiscoveryPublic, ...], Field(max_length=100)] = ()
    expired_count: Annotated[StrictInt, Field(ge=0, le=100)] = 0
    session_expires_at: UtcDatetime | None = None


class GameResultPublic(StrictRecord):
    game_id: UUID
    mode: GameMode = GameMode.SOLO
    phase: Literal["completed"] = "completed"
    score: Score
    total: Literal[5] = 5
    source: RankingSource
    curator_mode: CuratorMode
    answered_rounds: tuple[
        RevealedRoundPublic,
        RevealedRoundPublic,
        RevealedRoundPublic,
        RevealedRoundPublic,
        RevealedRoundPublic,
    ]
    discoveries: Annotated[tuple[DiscoveryPublic, ...], Field(max_length=100)] = ()
    expires_at: UtcDatetime

    @model_validator(mode="after")
    def complete_five(self):
        validate_provenance(self.curator_mode, self.source)
        if [round_.ordinal for round_ in self.answered_rounds] != [1, 2, 3, 4, 5]:
            raise ValueError("Results must contain the ordered five accepted rounds")
        if len({round_.round_id for round_ in self.answered_rounds}) != 5:
            raise ValueError("Results cannot repeat a round")
        if any(
            round_.game_id != self.game_id or round_.source != self.source for round_ in self.answered_rounds
        ):
            raise ValueError("Results contain a different game or source")
        if sum(round_.correct for round_ in self.answered_rounds) != self.score:
            raise ValueError("Result score disagrees with accepted answers")
        prefix_score = 0
        contestants: set[UUID] = set()
        for round_ in self.answered_rounds:
            prefix_score += int(round_.correct)
            if round_.cumulative_score != prefix_score:
                raise ValueError("Accepted round cumulative scores are inconsistent")
            for choice in round_.choices:
                if choice.entity.id in contestants:
                    raise ValueError("Results cannot repeat a contestant")
                contestants.add(choice.entity.id)
        return self


class ChallengeInvitationPublic(StrictRecord):
    creator_name: Nickname | None = None
    slug: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{22,80}$")]
    seed: EntityPublic
    creator_score: Score
    total: Literal[5] = 5
    source: RankingSource
    expires_at: UtcDatetime

    @model_validator(mode="after")
    def explicit_source(self):
        if self.seed.source != self.source:
            raise ValueError("Challenge seed and source disagree")
        return self


class ChallengeCreatedPublic(StrictRecord):
    invitation: ChallengeInvitationPublic
    # Relative to the verified canonical web origin; no arbitrary external URL.
    share_path: Annotated[str, StringConstraints(pattern=r"^/c/[A-Za-z0-9_-]{22,80}$")]

    @model_validator(mode="after")
    def matching_slug(self):
        if self.share_path != f"/c/{self.invitation.slug}":
            raise ValueError("Share path must reference this invitation")
        return self


class DuelOutcomePublic(StrictRecord):
    attempt_id: UUID
    attempt_number: Annotated[StrictInt, Field(ge=1)]
    completed_at: UtcDatetime
    creator_name: Nickname | None
    challenger_name: Nickname | None
    creator_score: Score
    challenger_score: Score
    outcome: Literal["creator", "challenger", "tie"]


class DuelResultsPublic(StrictRecord):
    status: Literal["not_shared", "active", "retired"] = "active"
    expires_at: UtcDatetime | None = None
    replay_slug: Annotated[str | None, StringConstraints(pattern=r"^[A-Za-z0-9_-]{22,80}$")] = None
    next_cursor: Annotated[str | None, StringConstraints(max_length=160)] = None
    outcomes: Annotated[tuple[DuelOutcomePublic, ...], Field(max_length=20)] = ()


class HealthPublic(StrictRecord):
    status: Literal["ok", "unavailable"]
    component: Literal["api"] = "api"
    generation_available: StrictBool = False


class FieldErrorPublic(StrictRecord):
    loc: Annotated[
        tuple[
            Annotated[str, StringConstraints(max_length=64)] | Annotated[StrictInt, Field(ge=0, le=10_000)],
            ...,
        ],
        Field(max_length=8),
    ]
    type: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,63}$")]


class ErrorPublic(StrictRecord):
    code: Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]{0,63}$")]
    message: Message
    retryable: StrictBool
    request_id: UUID
    field_errors: Annotated[tuple[FieldErrorPublic, ...], Field(max_length=16)] = ()
    retry_after_seconds: Annotated[StrictInt, Field(ge=0, le=3600)] | None = None


class ErrorEnvelope(StrictRecord):
    error: ErrorPublic
