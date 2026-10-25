"""Bounded shared values; importing them performs no I/O."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, StrictInt, StringConstraints


class StrictRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True, str_strip_whitespace=True)


class EntityType(StrEnum):
    ARTIST = "artist"
    MOVIE = "movie"


class CuratorMode(StrEnum):
    GENUINE_AGENT = "genuine_agent"
    DETERMINISTIC_QLOO = "deterministic_qloo"
    FIXTURE = "fixture"


class RankingSource(StrEnum):
    QLOO = "qloo"
    FIXTURE = "fixture"


class GameMode(StrEnum):
    SOLO = "solo"
    FIXED = "fixed"


class GamePhase(StrEnum):
    PREPARING = "preparing"
    READY = "ready"
    PLAYING = "playing"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class GenerationStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class RejectionReason(StrEnum):
    INVALID_IDENTITY = "invalid_identity"
    WRONG_TYPE = "wrong_type"
    SELF_PAIR = "self_pair"
    DUPLICATE_ENTITY = "duplicate_entity"
    MISSING_SCORE = "missing_score"
    NONFINITE_SCORE = "nonfinite_score"
    SCORE_TIE = "score_tie"
    NEAR_TIE = "near_tie"
    CONTRADICTORY_ORDER = "contradictory_order"
    INSUFFICIENT_METADATA = "insufficient_metadata"
    UNSUPPORTED_RIGHTS = "unsupported_rights"


def normalize_utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


UtcDatetime = Annotated[AwareDatetime, AfterValidator(normalize_utc)]
Count = Annotated[StrictInt, Field(ge=0, le=1000)]
Revision = Annotated[StrictInt, Field(ge=0, le=2_147_483_647)]
Score = Annotated[StrictInt, Field(ge=0, le=5)]
Ordinal = Annotated[StrictInt, Field(ge=1, le=5)]
ShortText = Annotated[str, StringConstraints(min_length=1, max_length=200)]
VersionToken = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:+/-]{0,99}$")]


def validate_provenance(mode: CuratorMode, source: RankingSource) -> None:
    if (mode == CuratorMode.FIXTURE) != (source == RankingSource.FIXTURE):
        raise ValueError("Curator mode and ranking source disagree")
