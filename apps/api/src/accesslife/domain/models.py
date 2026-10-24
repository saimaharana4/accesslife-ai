from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo
from pydantic import BaseModel, Field, model_validator

AccessStatus = Literal["confirmed", "limited", "inaccessible", "unknown"]
CityId = Literal["london", "new-york", "paris", "berlin", "chicago"]


class City(BaseModel):
    id: CityId
    name: str
    time_zone: str
    latitude: float
    longitude: float
    district: str
    coverage: str = "limited"
    limitation: str = "Curated venue evidence; door-to-door wheelchair routes are not verified."


class Fact(BaseModel):
    feature: str
    status: AccessStatus = "unknown"
    evidence_ids: list[str] = Field(default_factory=list)
    conflict: bool = False
    stale: bool = False
    conditions: str | None = None


class Evidence(BaseModel):
    id: str
    source_url: str
    title: str
    source_type: str = "official_venue"
    claim: str
    retrieved_at: str
    source_updated_at: str | None = None
    rights: str = "Original factual summary; linked source retains its own copyright."
    transformation_version: str = "manual-summary-v1"


class Place(BaseModel):
    id: str
    city_id: CityId
    name: str
    category: str
    latitude: float
    longitude: float
    interests: list[str]
    description: str
    facts: list[Fact]
    source_url: str


class Mobility(BaseModel):
    required_features: list[Literal["step_free_entrance", "accessible_toilet", "lift"]] = Field(
        default_factory=lambda: ["step_free_entrance"]
    )
    accepted_limitations: list[str] = Field(default_factory=list)
    max_leg_distance_m: int = Field(default=500, ge=0, le=10000)
    max_total_distance_m: int = Field(default=2000, ge=0, le=50000)
    rest_every_minutes: int = Field(default=45, ge=10, le=180)
    max_transfers: int = Field(default=1, ge=0, le=5)


class Window(BaseModel):
    starts_at: datetime
    ends_at: datetime
    time_zone: str

    @model_validator(mode="after")
    def valid_window(self):
        try:
            zone = ZoneInfo(self.time_zone)
        except (KeyError, ValueError) as exc:
            raise ValueError("Choose a valid city time zone") from exc
        for value in (self.starts_at, self.ends_at):
            if value.utcoffset() is None or value.astimezone(zone).utcoffset() != value.utcoffset():
                raise ValueError("Use explicit timestamps with the city's correct UTC offset")
        if self.ends_at <= self.starts_at:
            raise ValueError("The outing must end after it starts")
        if (self.ends_at - self.starts_at).total_seconds() > 12 * 3600:
            raise ValueError("Choose an outing of at most twelve hours")
        return self


class Interest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: str = Field(default="culture", max_length=40)


class PlanInput(BaseModel):
    city_id: CityId
    window: Window
    mobility: Mobility = Field(default_factory=Mobility)
    interests: list[Interest] = Field(default_factory=list, max_length=12)
    intent: str = Field(default="", max_length=1200)
    trip_id: str | None = None
    segment_id: str | None = None


class ReplanInput(BaseModel):
    expected_version: int = Field(ge=1)
    inputs: PlanInput


class TripSegment(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    city_id: CityId
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    plan_id: str | None = None
    plan_version: int | None = None


class TripInput(BaseModel):
    title: str = Field(default="My city collection", min_length=1, max_length=100)
    segments: list[TripSegment] = Field(default_factory=list, max_length=12)
    expected_revision: int | None = None

    @model_validator(mode="after")
    def validate_segments(self):
        dates = [datetime.strptime(s.date, "%Y-%m-%d").date() for s in self.segments]
        if dates != sorted(dates):
            raise ValueError("City segments must be in chronological order")
        if len({s.id for s in self.segments}) != len(self.segments):
            raise ValueError("Segment identifiers must be unique")
        return self


class Explanation(BaseModel):
    # The model chooses a useful narrative frame, never new operational facts.
    summary: Literal[
        "This is a provisional cultural outing. Review the venue evidence and verify opening hours and every travel leg before relying on it.",
        "Your interests shape this outline, while your requirements remain separate checks. Confirm the missing journey and opening information before you travel.",
        "Use this outline as a starting point for a relaxed cultural day. Venue statements are linked below; routes, timings and rest facilities still need checking.",
    ]
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)


class IntentResult(BaseModel):
    interests: list[str] = Field(default_factory=list, max_length=8)
    clarification: str | None = None


def eligibility(place: Place, mobility: Mobility, available_evidence_ids: set[str]) -> tuple[bool, list[str]]:
    facts = {f.feature: f for f in place.facts}
    issues = []
    for feature in mobility.required_features:
        fact = facts.get(feature)
        passed = (
            fact
            and fact.evidence_ids
            and all(eid in available_evidence_ids for eid in fact.evidence_ids)
            and not fact.conflict
            and not fact.stale
            and (
                fact.status == "confirmed"
                or (
                    fact.status == "limited"
                    and bool(fact.conditions)
                    and feature in mobility.accepted_limitations
                )
            )
        )
        if not passed:
            issues.append(f"{feature.replace('_', ' ')} requires current compatible evidence")
    return not issues, issues


class TasteResult(BaseModel):
    provider: str
    label: str
    order: list[str]
    matches: dict[str, list[str]] = Field(default_factory=dict)
    warning: str | None = None
    live: bool
    scores: dict[str, float] = Field(default_factory=dict)
    unmapped: list[str] = Field(default_factory=list)
    score_semantics: str | None = None


class EligiblePlace(Place):
    issues: list[str] = Field(default_factory=list)
    venue_eligible: bool


class Stop(BaseModel):
    place: Place
    status: Literal["provisional"]
    suggested_visit_minutes: int
    rest_every_minutes: int
    opening_hours_status: Literal["unknown"]


class Leg(BaseModel):
    from_id: str
    to_id: str
    status: Literal["unknown"]
    distance_m: int | None = None
    distance_lower_bound_m: int
    duration_seconds: int | None = None
    message: str


class Passage(BaseModel):
    id: str
    text: str
    source_title: str
    source_url: str


class KnowledgeResult(BaseModel):
    status: str
    passages: list[Passage]


class EnvironmentResult(BaseModel):
    weather: dict
    transport: dict
    knowledge: KnowledgeResult


class ExplanationResult(BaseModel):
    summary: str
    provider: str
    error: str | None = None


class PlanDiff(BaseModel):
    from_version: int
    removed: list[str]
    added: list[str]


class PlanSnapshot(BaseModel):
    id: str
    version: int
    inputs: PlanInput
    status: str
    confirmed: bool
    stops: list[Stop]
    legs: list[Leg]
    candidates: list[EligiblePlace]
    verification_needed: list[EligiblePlace]
    taste: TasteResult
    baseline_order: list[str]
    environment: EnvironmentResult
    explanation: ExplanationResult
    unresolved: list[str]
    evidence: list[Evidence]
    distance_lower_bound_total_m: int
    diff: PlanDiff | None = None


class PendingPlan(BaseModel):
    id: str
    version: Literal[0]
    status: Literal["pending"]


class TripSnapshot(BaseModel):
    id: str
    title: str
    revision: int
    segments: list[TripSegment]
    transfer_status: Literal["user_arranged_unverified"]
    transfers: list[dict[str, str]]


class IntentInput(BaseModel):
    text: str = Field(min_length=1, max_length=1200)
