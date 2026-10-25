"""Read port values. Persistence rows and unrestricted provider data stay behind it."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from tasteduel.domain.curation import CurationReceipt


@dataclass(frozen=True)
class EntityRead:
    id: UUID
    name: str
    entity_type: str
    source: str
    asset_id: str | None


@dataclass(frozen=True)
class ChoiceRead:
    id: UUID
    entity: EntityRead


@dataclass(frozen=True)
class AcceptedRead:
    selected_choice_id: UUID
    winning_choice_id: UUID
    correct: bool
    accepted_at: datetime
    cumulative_score: int


@dataclass(frozen=True)
class RoundRead:
    id: UUID
    ordinal: int
    target_type: str
    retrieved_at: datetime
    choices: tuple[ChoiceRead, ChoiceRead]
    accepted: AcceptedRead | None


@dataclass(frozen=True)
class GameRead:
    id: UUID
    session_id: UUID
    phase: str
    mode: str
    revision: int
    current_ordinal: int
    answered_count: int
    score: int
    expires_at: datetime
    seed: EntityRead
    receipt: CurationReceipt
    current: RoundRead | None


@dataclass(frozen=True)
class DiscoveryRead:
    entity: EntityRead
    saved_at: datetime
    expires_at: datetime


class ReadRepository(Protocol):
    def game(self, game_id: UUID) -> GameRead | None: ...
    def answered_rounds(self, game_id: UUID) -> tuple[RoundRead, ...]: ...
    def discoveries(self) -> tuple[DiscoveryRead, ...]: ...
