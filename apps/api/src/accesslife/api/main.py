import asyncio
import hashlib
import json
import secrets
import logging
from datetime import timedelta
from uuid import uuid4
from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import select, func, text
from sqlalchemy.exc import IntegrityError
from accesslife.config import settings
from accesslife.domain.models import (
    City,
    Place,
    Evidence,
    PlanInput,
    ReplanInput,
    TripInput,
    IntentResult,
    IntentInput,
    PlanSnapshot,
    PendingPlan,
    TripSnapshot,
)
from accesslife.persistence.db import Session, SessionRow, PlanRow, RunRow, VersionRow, EventRow, TripRow, now
from accesslife.application.runs import append_event, fingerprint, dispatcher, TERMINAL
from accesslife.adapters.catalogue import CITIES, CITY_BY_ID, EVIDENCE
from accesslife.adapters.environment import discover_osm
from accesslife.composition import places_provider
from accesslife.adapters.generation import generate, safe_prompt
from accesslife.application.limits import quota
from accesslife.ports.providers import ProviderError

app = FastAPI(title="AccessLife API", version="0.1.0")


@app.middleware("http")
async def boundaries(request, call_next):
    request.state.request_id = str(uuid4())
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") != settings().app_public_url.rstrip("/"):
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "origin_denied",
                        "message": "Request origin is not allowed",
                        "retryable": False,
                    }
                },
            )
        if int(request.headers.get("content-length", "0")) > 20000:
            return JSONResponse(
                status_code=413,
                content={
                    "error": {"code": "payload_too_large", "message": "Request too large", "retryable": False}
                },
            )
    try:
        response = await call_next(request)
    except Exception as exc:
        logging.getLogger("accesslife").error(
            json.dumps(
                {
                    "event": "request_failed",
                    "request_id": request.state.request_id,
                    "error_type": type(exc).__name__,
                }
            )
        )
        response = JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "The request could not be completed. Please retry.",
                    "retryable": True,
                    "request_id": request.state.request_id,
                }
            },
        )
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.exception_handler(HTTPException)
async def safe_error(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": str(exc.detail),
                "message": str(exc.detail).replace("_", " "),
                "retryable": exc.status_code in {429, 503},
                "request_id": request.state.request_id,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def invalid_input(request, exc):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "request_id": request.state.request_id,
                "code": "invalid_input",
                "message": "Check the city, dates and mobility inputs",
                "retryable": False,
                "fields": [
                    {"field": ".".join(str(x) for x in e["loc"]), "message": e["msg"]} for e in exc.errors()
                ],
            }
        },
    )


@app.exception_handler(ProviderError)
async def safe_provider_error(request, exc):
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "request_id": request.state.request_id,
                "code": exc.code,
                "message": "This provider is temporarily unavailable. Please retry.",
                "retryable": exc.retryable,
            }
        },
    )


def identity(request: Request):
    token = request.cookies.get("accesslife_session", "")
    sid = hashlib.sha256(token.encode()).hexdigest()
    with Session() as db:
        session = db.get(SessionRow, sid)
        if not session or session.expires_at <= now():
            raise HTTPException(401, "session_expired")
    return sid


def owned(db, model, resource_id, sid, lock=False):
    query = select(model).where(model.id == resource_id, model.session_id == sid)
    if lock:
        query = query.with_for_update()
    value = db.scalar(query)
    if not value:
        raise HTTPException(404, "not_found")
    return value


@app.post("/v1/sessions")
def create_session(response: Response):
    token = secrets.token_urlsafe(32)
    with Session.begin() as db:
        db.add(
            SessionRow(
                id=hashlib.sha256(token.encode()).hexdigest(),
                expires_at=now() + timedelta(hours=settings().session_retention_hours),
            )
        )
    response.set_cookie(
        "accesslife_session",
        token,
        max_age=settings().session_retention_hours * 3600,
        httponly=True,
        secure=settings().app_env == "production",
        samesite="lax",
        path="/",
    )
    return {"status": "active", "retention_hours": settings().session_retention_hours}


@app.delete("/v1/sessions/current")
def clear_session(response: Response, sid=Depends(identity)):
    with Session.begin() as db:
        db.delete(db.get(SessionRow, sid))
    response.delete_cookie("accesslife_session", path="/")
    return {"status": "cleared"}


@app.get("/v1/sessions/current")
def current_session(sid=Depends(identity)):
    with Session() as db:
        run = db.scalar(
            select(RunRow)
            .where(RunRow.session_id == sid, RunRow.status.in_(["queued", "running"]))
            .order_by(RunRow.created_at.desc())
            .limit(1)
        )
        return {"status": "active", "active_run": {"run_id": run.id, "plan_id": run.plan_id} if run else None}


@app.get("/v1/cities", response_model=list[City])
def cities():
    return CITIES


@app.get("/v1/providers")
def providers():
    cfg = settings()
    return {
        "taste": cfg.taste_provider,
        "qloo_configured": bool(cfg.qloo_api_key or cfg.qloo_api_key_secret),
        "generation": cfg.generation_provider,
        "live_qloo_validated": "Determined per plan from actual successful provider results",
    }


@app.get("/v1/places", response_model=list[Place])
def places(city_id: str):
    if city_id not in CITY_BY_ID:
        raise HTTPException(422, "invalid_city")
    return places_provider.search(city_id)


@app.get("/v1/cities/{city_id}/discover")
async def osm(city_id: str, sid=Depends(identity)):
    if city_id not in CITY_BY_ID:
        raise HTTPException(404, "not_found")
    return await discover_osm(city_id)


@app.get("/v1/evidence/{evidence_id}", response_model=Evidence)
def evidence(evidence_id: str):
    # Only the public, original venue summaries are exposed by this route.
    if evidence_id not in EVIDENCE:
        raise HTTPException(404, "not_found")
    return EVIDENCE[evidence_id]


@app.post("/v1/intent")
async def interpret(body: IntentInput, sid=Depends(identity)):
    try:
        quota(f"intent-{sid}", 30, 3600)
    except ProviderError as exc:
        raise HTTPException(429, "intent_limit_reached") from exc
    intent = body.text
    try:
        result, provider = await generate(
            safe_prompt(
                {
                    "task": "Extract only explicitly mentioned cultural interests; do not infer mobility limits.",
                    "untrusted_user_text": intent,
                }
            ),
            IntentResult,
            IntentInput,
        )
        return {**result.model_dump(), "provider": provider, "requires_review": True}
    except Exception:
        return {
            "interests": [],
            "clarification": "Please select your interests using the labeled controls.",
            "provider": "template",
            "requires_review": True,
        }


def submit(inputs: PlanInput, key: str, sid: str, plan_id=None, expected=None):
    if not key or len(key) > 128:
        raise HTTPException(422, "idempotency_key_required")
    if inputs.window.time_zone != CITY_BY_ID[inputs.city_id].time_zone:
        raise HTTPException(422, "city_timezone_mismatch")
    data = inputs.model_dump(mode="json")
    hashed = fingerprint({"inputs": data, "plan_id": plan_id, "expected": expected})
    try:
        with Session.begin() as db:
            db.execute(text("SELECT pg_advisory_xact_lock(741803)"))
            previous = db.scalar(
                select(RunRow).where(RunRow.session_id == sid, RunRow.idempotency_key == key)
            )
            if previous:
                if previous.input_hash != hashed:
                    raise HTTPException(409, "idempotency_input_conflict")
                run_id, pid = previous.id, previous.plan_id
            else:
                try:
                    quota(
                        f"planning-global-{now().date().isoformat()}",
                        settings().max_daily_planning_runs,
                        86400,
                    )
                except ProviderError as exc:
                    raise HTTPException(429, "daily_planning_capacity_reached") from exc
                count = db.scalar(
                    select(func.count())
                    .select_from(RunRow)
                    .where(RunRow.session_id == sid, RunRow.created_at > now() - timedelta(hours=1))
                )
                queued = db.scalar(
                    select(func.count()).select_from(RunRow).where(RunRow.status.in_(["queued", "running"]))
                )
                if count >= 30 or queued >= 30:
                    raise HTTPException(429, "planning_limit_reached")
                if plan_id:
                    plan = owned(db, PlanRow, plan_id, sid, True)
                    if plan.version != expected:
                        raise HTTPException(409, "plan_version_conflict")
                    plan.generation += 1
                    for old in db.scalars(
                        select(RunRow)
                        .where(RunRow.plan_id == plan.id, RunRow.status.in_(["queued", "running"]))
                        .with_for_update()
                    ):
                        old.status = "superseded"
                        append_event(db, old, "supervisor", "superseded", "A newer request replaced this run")
                else:
                    plan = PlanRow(id=str(uuid4()), session_id=sid, version=0, generation=1)
                    db.add(plan)
                    db.flush()
                if inputs.trip_id:
                    trip = owned(db, TripRow, inputs.trip_id, sid, True)
                    segment = next((s for s in trip.data["segments"] if s["id"] == inputs.segment_id), None)
                    if (
                        not segment
                        or segment["city_id"] != inputs.city_id
                        or segment["date"] != inputs.window.starts_at.date().isoformat()
                    ):
                        raise HTTPException(422, "trip_segment_mismatch")
                    data["_trip_revision"] = trip.revision
                run_id, pid = str(uuid4()), plan.id
                run = RunRow(
                    id=run_id,
                    plan_id=pid,
                    session_id=sid,
                    idempotency_key=key,
                    input_hash=hashed,
                    inputs=data,
                    generation=plan.generation,
                    created_at=now(),
                    checkpoint={},
                )
                db.add(run)
                db.flush()
                append_event(db, run, "supervisor", "queued", "Your plan is queued")
    except IntegrityError as exc:
        raise HTTPException(409, "concurrent_request_retry") from exc
    try:
        dispatcher().enqueue(run_id)
    except Exception as exc:
        raise HTTPException(503, "dispatch_pending_retry_same_key") from exc
    return {"plan_id": pid, "run_id": run_id, "events_url": f"/api/v1/runs/{run_id}/events"}


@app.post("/v1/plans", status_code=202)
def new_plan(inputs: PlanInput, request: Request, sid=Depends(identity)):
    return submit(inputs, request.headers.get("idempotency-key", ""), sid)


@app.post("/v1/plans/{plan_id}/replan", status_code=202)
def replan(plan_id: str, body: ReplanInput, request: Request, sid=Depends(identity)):
    return submit(
        body.inputs, request.headers.get("idempotency-key", ""), sid, plan_id, body.expected_version
    )


@app.get("/v1/plans/{plan_id}", response_model=PlanSnapshot | PendingPlan)
def get_plan(plan_id: str, version: int | None = None, sid=Depends(identity)):
    if version is not None and version < 1:
        raise HTTPException(422, "invalid_plan_version")
    with Session() as db:
        plan = owned(db, PlanRow, plan_id, sid)
        result = db.scalar(
            select(VersionRow).where(
                VersionRow.plan_id == plan_id, VersionRow.version == (version or plan.version)
            )
        )
        if result is None and version is not None:
            raise HTTPException(404, "plan_version_not_found")
        return result.data if result else {"id": plan_id, "version": 0, "status": "pending"}


@app.get("/v1/plans")
def list_plans(sid=Depends(identity)):
    with Session() as db:
        rows = db.execute(
            select(PlanRow, VersionRow)
            .join(VersionRow, (VersionRow.plan_id == PlanRow.id) & (VersionRow.version == PlanRow.version))
            .where(PlanRow.session_id == sid)
        ).all()
        return [{"id": p.id, "version": p.version, "city_id": v.data["inputs"]["city_id"]} for p, v in rows]


@app.get("/v1/plans/{plan_id}/impact")
def impact(plan_id: str, version: int | None = None, sid=Depends(identity)):
    plan = get_plan(plan_id, version, sid)
    return {
        "provider": plan.get("taste", {}).get("provider"),
        "baseline": plan.get("baseline_order", []),
        "taste": plan.get("taste", {}),
        "version": plan["version"],
        "candidate_set": [p["id"] for p in plan.get("candidates", [])],
        "baseline_policy": "Stable place ID: verified travel durations unavailable; category matching appears only in the development ranking.",
    }


@app.post("/v1/runs/{run_id}/cancel")
def cancel(run_id: str, sid=Depends(identity)):
    with Session.begin() as db:
        run = owned(db, RunRow, run_id, sid, True)
        if run.status not in TERMINAL:
            run.status = "cancelled"
            append_event(
                db, run, "supervisor", "cancelled", "Planning cancelled; published versions remain available"
            )
    return {"status": "cancelled"}


@app.get("/v1/runs/{run_id}/events")
async def events(run_id: str, request: Request, sid=Depends(identity)):
    with Session() as db:
        owned(db, RunRow, run_id, sid)
    try:
        after = max(0, int(request.headers.get("last-event-id", "0")))
    except ValueError as exc:
        raise HTTPException(422, "invalid_event_id") from exc

    async def stream():
        nonlocal after
        for _ in range(100):
            if await request.is_disconnected():
                break
            with Session() as db:
                run = db.get(RunRow, run_id)
                if not run:
                    break
                rows = list(
                    db.scalars(
                        select(EventRow)
                        .where(EventRow.run_id == run_id, EventRow.sequence > after)
                        .order_by(EventRow.sequence)
                    )
                )
                terminal = run.status in TERMINAL
            for row in rows:
                after = row.sequence
                yield f"id: {row.sequence}\ndata: {json.dumps(row.data)}\n\n"
            if terminal:
                break
            yield ": heartbeat\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})


def trip_view(trip):
    segments = trip.data["segments"]
    return {
        "id": trip.id,
        "revision": trip.revision,
        **trip.data,
        "transfer_status": "user_arranged_unverified",
        "transfers": [
            {"from": a["city_id"], "to": b["city_id"], "status": "user_arranged_unverified"}
            for a, b in zip(segments, segments[1:])
        ],
    }


def validate_attachments(db, body, sid):
    for segment in body.segments:
        if segment.plan_id:
            plan = owned(db, PlanRow, segment.plan_id, sid)
            version = db.scalar(
                select(VersionRow).where(
                    VersionRow.plan_id == plan.id, VersionRow.version == segment.plan_version
                )
            )
            if (
                not version
                or version.data["inputs"]["city_id"] != segment.city_id
                or version.data["inputs"]["window"]["starts_at"][:10] != segment.date
            ):
                raise HTTPException(422, "plan_segment_mismatch")
        elif segment.plan_version is not None:
            raise HTTPException(422, "plan_id_required")


@app.post("/v1/trips", status_code=201)
def create_trip(body: TripInput, sid=Depends(identity)):
    with Session.begin() as db:
        validate_attachments(db, body, sid)
        trip = TripRow(
            id=str(uuid4()), session_id=sid, revision=1, data=body.model_dump(exclude={"expected_revision"})
        )
        db.add(trip)
        db.flush()
        return trip_view(trip)


@app.get("/v1/trips", response_model=list[TripSnapshot])
def list_trips(sid=Depends(identity)):
    with Session() as db:
        return [trip_view(t) for t in db.scalars(select(TripRow).where(TripRow.session_id == sid))]


@app.get("/v1/trips/{trip_id}", response_model=TripSnapshot)
def get_trip(trip_id: str, sid=Depends(identity)):
    with Session() as db:
        return trip_view(owned(db, TripRow, trip_id, sid))


@app.patch("/v1/trips/{trip_id}", response_model=TripSnapshot)
def edit_trip(trip_id: str, body: TripInput, sid=Depends(identity)):
    with Session.begin() as db:
        trip = owned(db, TripRow, trip_id, sid, True)
        if trip.revision != body.expected_revision:
            raise HTTPException(409, "trip_revision_conflict")
        validate_attachments(db, body, sid)
        trip.data = body.model_dump(exclude={"expected_revision"})
        trip.revision += 1
        return trip_view(trip)


@app.get("/v1/health/live")
def live():
    return {"status": "ok"}


@app.get("/v1/health/ready")
def ready():
    try:
        with Session() as db:
            db.execute(text("SELECT 1 FROM sessions LIMIT 1"))
        return {"status": "ready", "taste": settings().taste_provider}
    except Exception as exc:
        raise HTTPException(503, "database_not_ready") from exc
