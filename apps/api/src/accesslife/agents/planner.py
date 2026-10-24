import asyncio
from math import radians, sin, cos, atan2, sqrt
from typing import TypedDict
from uuid import uuid4
from langgraph.graph import StateGraph, START, END
from sqlalchemy import select
from accesslife.config import settings
from accesslife.domain.models import PlanInput, Explanation, Place, eligibility
from accesslife.ports.providers import ProviderError
from accesslife.composition import (
    places_provider,
    evidence_provider,
    weather_provider,
    transit_provider,
    knowledge_retriever,
    taste_provider,
    generate_structured,
    development_taste_provider,
)
from accesslife.adapters.generation import safe_prompt
from accesslife.persistence.db import Session, RunRow, PlanRow, VersionRow, TripRow
from accesslife.application.runs import ensure_current, append_event
from accesslife.application.limits import RUN_CONTEXT


class GraphState(TypedDict):
    run_id: str
    token: str
    inputs: dict
    checkpoint: dict


def distance(a, b):
    lat = radians(b.latitude - a.latitude)
    lon = radians(b.longitude - a.longitude)
    v = sin(lat / 2) ** 2 + cos(radians(a.latitude)) * cos(radians(b.latitude)) * sin(lon / 2) ** 2
    return round(6371000 * 2 * atan2(sqrt(v), sqrt(1 - v)))


def checkpoint(state, stage, payload, summary):
    with Session.begin() as db:
        run = ensure_current(db, state["run_id"], state["token"])
        saved = {**run.checkpoint, stage: payload}
        run.checkpoint = saved
        evidence_ids = [
            eid
            for item in saved.get("ranking", {}).get("eligible", [])
            for fact in item["facts"]
            for eid in fact["evidence_ids"]
        ]
        append_event(db, run, stage, "completed", summary, len(set(evidence_ids)))
        state["checkpoint"] = saved
    return state


async def gather(state):
    if "sources" in state["checkpoint"]:
        return state
    inputs = PlanInput.model_validate(state["inputs"])

    async def guidance():
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(
                    knowledge_retriever.retrieve,
                    " ".join(i.name for i in inputs.interests) + " accessibility",
                    inputs.city_id,
                ),
                7,
            )
        except Exception:
            return {"status": "unavailable", "passages": []}

    forecast, transport, knowledge = await asyncio.gather(
        weather_provider.forecast(inputs.city_id, inputs.window.starts_at.date().isoformat()),
        transit_provider.capabilities(inputs.city_id),
        guidance(),
    )
    return checkpoint(
        state,
        "sources",
        {"weather": forecast, "transport": transport, "knowledge": knowledge},
        "Gathered available weather, transport and source guidance",
    )


async def rank(state):
    if "ranking" in state["checkpoint"]:
        return state
    inputs = PlanInput.model_validate(state["inputs"])
    candidates = places_provider.search(inputs.city_id)
    eligible, verification = [], []
    for p in candidates:
        available = set(evidence_provider.lookup([eid for fact in p.facts for eid in fact.evidence_ids]))
        passed, issues = eligibility(p, inputs.mobility, available)
        (eligible if passed else verification).append(
            {**p.model_dump(), "issues": issues, "venue_eligible": passed}
        )
    pool = [p for p in candidates if any(e["id"] == p.id for e in eligible)]
    if not pool:
        taste = await development_taste_provider().rank_candidates([], [])
        taste["warning"] = (
            "No venue meets the mandatory evidence requirements. Taste cannot override missing access evidence."
        )
    else:
        try:
            provider = await asyncio.wait_for(asyncio.to_thread(taste_provider), 3)
            taste = await asyncio.wait_for(
                provider.rank_candidates(pool, [i.name for i in inputs.interests]), 10
            )
        except (ProviderError, asyncio.TimeoutError, KeyError, TypeError, ValueError) as exc:
            taste = await development_taste_provider().rank_candidates(
                pool, [i.name for i in inputs.interests]
            )
            taste["warning"] = (
                f"Qloo unavailable ({getattr(exc, 'code', 'provider_error')}); development category matching is active."
            )
    baseline = sorted(pool, key=lambda p: p.id)
    # No supported travel durations exist yet, so the duration tie is explicit.
    return checkpoint(
        state,
        "ranking",
        {
            "eligible": eligible,
            "verification": verification,
            "taste": taste,
            "baseline": [p.id for p in baseline],
        },
        "Checked mandatory venue facts and ranked only the eligible set",
    )


async def construct(state):
    if "itinerary" in state["checkpoint"]:
        return state
    inputs = PlanInput.model_validate(state["inputs"])
    ranking = state["checkpoint"]["ranking"]
    by_id = {p["id"]: p for p in ranking["eligible"] + ranking["verification"]}
    selected = [by_id[pid] for pid in ranking["taste"]["order"]][:3]
    if not selected:
        selected = ranking["verification"][:2]
    stops, legs, lower_bound_total = [], [], 0
    available_minutes = (inputs.window.ends_at - inputs.window.starts_at).total_seconds() / 60
    max_stops = min(3, max(0, int((available_minutes + 20) // 80)))
    for candidate in selected[:max_stops]:
        if stops:
            a = Place.model_validate(stops[-1]["place"])
            b = Place.model_validate(candidate)
            lower = distance(a, b)
            if (
                lower > inputs.mobility.max_leg_distance_m
                or lower_bound_total + lower > inputs.mobility.max_total_distance_m
            ):
                continue
            lower_bound_total += lower
            legs.append(
                {
                    "from_id": a.id,
                    "to_id": b.id,
                    "status": "unknown",
                    "distance_m": None,
                    "distance_lower_bound_m": lower,
                    "duration_seconds": None,
                    "message": "Straight-line lower bound only. Route distance, duration, kerbs, boarding and access are unverified.",
                }
            )
        stops.append(
            {
                "place": candidate,
                "status": "provisional",
                "suggested_visit_minutes": 60,
                "opening_hours_status": "unknown",
                "rest_every_minutes": inputs.mobility.rest_every_minutes,
            }
        )
    payload = {
        "stops": stops,
        "legs": legs,
        "status": "provisional" if stops else "no_feasible_draft",
        "confirmed": False,
        "unresolved": [
            "Opening windows and door-to-door route evidence require verification.",
            "Suggested visit durations are planning placeholders, not verified arrival times.",
        ],
        "distance_lower_bound_total_m": lower_bound_total,
    }
    return checkpoint(
        state,
        "itinerary",
        payload,
        "Built a provisional outline; unsupported journey claims remain unconfirmed",
    )


async def explain(state):
    if "explanation" in state["checkpoint"]:
        return state
    itinerary = state["checkpoint"]["itinerary"]
    ids = [eid for stop in itinerary["stops"] for f in stop["place"]["facts"] for eid in f["evidence_ids"]]
    summary = "This is a provisional cultural outing. Review the venue evidence and verify opening hours and every travel leg before relying on it."
    provider, error = "template", None
    try:
        result, provider = await asyncio.wait_for(
            generate_structured(
                safe_prompt(
                    {
                        "task": "Choose the most appropriate provisional summary frame; do not introduce venue facts.",
                        "stop_names": [s["place"]["name"] for s in itinerary["stops"]],
                        "unresolved": itinerary["unresolved"],
                        "allowed_evidence_ids": ids,
                    }
                ),
                Explanation,
            ),
            8,
        )
        if set(result.evidence_ids) - set(ids):
            raise ProviderError("unsupported_citation")
        summary = result.summary
    except Exception as exc:
        # Explanation is optional; retain deterministic facts. Never expose provider exception text.
        error = getattr(exc, "code", "generation_unavailable")
    return checkpoint(
        state,
        "explanation",
        {"summary": summary, "provider": provider, "error": error},
        "Prepared explanation; deterministic validation remains authoritative",
    )


def build_graph():
    graph = StateGraph(GraphState)
    for name, node in [
        ("sources", gather),
        ("ranking", rank),
        ("itinerary", construct),
        ("explanation", explain),
    ]:
        graph.add_node(name, node)
    graph.add_edge(START, "sources")
    graph.add_edge("sources", "ranking")
    graph.add_edge("ranking", "itinerary")
    graph.add_edge("itinerary", "explanation")
    graph.add_edge("explanation", END)
    return graph.compile()


async def execute(run_id, token):
    RUN_CONTEXT.set(run_id)
    with Session() as db:
        run = db.get(RunRow, run_id)
        if run is None:
            return  # Session clearing may delete a claimed run before execution starts.
        state = {"run_id": run_id, "token": token, "inputs": run.inputs, "checkpoint": run.checkpoint}
    try:
        state = await asyncio.wait_for(build_graph().ainvoke(state), settings().plan_deadline_seconds)
        with Session.begin() as db:
            run = ensure_current(db, run_id, token)
            plan = db.scalar(select(PlanRow).where(PlanRow.id == run.plan_id).with_for_update())
            saved = state["checkpoint"]
            version = plan.version + 1
            data = {
                "id": plan.id,
                "version": version,
                "inputs": run.inputs,
                **saved["itinerary"],
                "candidates": saved["ranking"]["eligible"],
                "verification_needed": saved["ranking"]["verification"],
                "taste": saved["ranking"]["taste"],
                "baseline_order": saved["ranking"]["baseline"],
                "environment": saved["sources"],
                "explanation": saved["explanation"],
                "evidence": [
                    e.model_dump()
                    for e in evidence_provider.lookup(
                        [
                            eid
                            for p in saved["ranking"]["eligible"] + saved["ranking"]["verification"]
                            for f in p["facts"]
                            for eid in f["evidence_ids"]
                        ]
                    ).values()
                ],
            }
            if plan.version:
                prior = db.scalar(
                    select(VersionRow).where(
                        VersionRow.plan_id == plan.id, VersionRow.version == plan.version
                    )
                )
                old = {s["place"]["id"] for s in prior.data["stops"]}
                new = {s["place"]["id"] for s in data["stops"]}
                data["diff"] = {
                    "from_version": plan.version,
                    "removed": sorted(old - new),
                    "added": sorted(new - old),
                }
            db.add(VersionRow(id=str(uuid4()), plan_id=plan.id, version=version, data=data))
            plan.version = version
            if run.inputs.get("trip_id"):
                trip = db.scalar(select(TripRow).where(TripRow.id == run.inputs["trip_id"]).with_for_update())
                if (
                    trip
                    and trip.session_id == run.session_id
                    and trip.revision == run.inputs.get("_trip_revision")
                ):
                    trip_data = json_copy(trip.data)
                    for segment in trip_data["segments"]:
                        if segment["id"] == run.inputs.get("segment_id"):
                            segment["plan_id"], segment["plan_version"] = plan.id, version
                    trip.data = trip_data
                    trip.revision += 1
            run.status = "completed"
            run.lease_until = None
            append_event(
                db,
                run,
                "supervisor",
                "completed",
                f"Provisional plan version {version} saved",
                len(data["evidence"]),
            )
    except Exception as exc:
        with Session.begin() as db:
            run = db.scalar(select(RunRow).where(RunRow.id == run_id).with_for_update())
            if run and run.status == "running" and run.lease_token == token:
                run.status = "failed"
                run.lease_until = None
                append_event(
                    db,
                    run,
                    "supervisor",
                    "failed",
                    "Planning exceeded its deadline or could not complete. Your previous plan is preserved.",
                )
        if str(exc) == "run_obsolete":
            return


def json_copy(value):
    import json

    return json.loads(json.dumps(value))
