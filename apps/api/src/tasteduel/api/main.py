"""Taste Duel authoritative local API with opt-in private provider lifecycle.

Run separately from accesslife.api.main; no automatic migration or import I/O.
Generation is awaited and fenced; no post-response background execution.
"""

from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime, timedelta
from dataclasses import replace
import asyncio
import hashlib
import hmac
import re
import secrets
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import FastAPI, Header, Path, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException
from pydantic import ValidationError

from tasteduel.adapters.read_repository import SqlReadRepository
from tasteduel.adapters.usage_budget import ModelDailyBudget, UsageDenied, reserve
from tasteduel.api import presenters, schemas as s
from tasteduel.api.body_limit import BoundedBodyMiddleware
from tasteduel.application.errors import AppError
from tasteduel.application.discoveries import DiscoveryService
from tasteduel.application.challenges import ChallengeService
from tasteduel.application.entity_search import remember_search_entities
from tasteduel.application.gameplay import GameplayService, GenerationObservation
from tasteduel.application.reads import ReadService
from tasteduel.api.provider_runtime import ProviderStartupFailure, build_qloo_runtime
from tasteduel.config import Settings
from tasteduel.domain.types import EntityType
from tasteduel.persistence import models as m
from tasteduel.persistence.db import local_engine, scoped_session
from tasteduel.ports.qloo import ResolveSeedRequest

Key = Annotated[
    str, Header(alias="Idempotency-Key", min_length=16, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
]
ERRORS = {
    code: {"model": s.ErrorEnvelope} for code in (401, 403, 404, 408, 409, 410, 413, 422, 429, 501, 503)
}


def create_app(
    settings: Settings | None = None, *, engine: Engine | None = None, qloo_factory=None, generator=None
) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        runtime = None
        model = None
        app.state.generator = generator
        app.state.qloo = None
        app.state.qloo_status = "disabled"
        if settings.qloo_enabled:
            try:
                runtime = await (qloo_factory or build_qloo_runtime)(settings, database())
                app.state.qloo = runtime.port
                app.state.qloo_status = "ready"
            except ProviderStartupFailure as failure:
                app.state.qloo_status = failure.code
            except (AppError, SQLAlchemyError):
                app.state.qloo_status = "QLOO_DATABASE_UNAVAILABLE"
        if generator is None and settings.generation_enabled and app.state.qloo is not None:
            from tasteduel.adapters.vertex_curator import MODEL, VertexCuratorModel
            from tasteduel.agents.round_curator import RoundCuratorAgent

            try:
                async with asyncio.timeout(5):
                    model = await asyncio.to_thread(
                        VertexCuratorModel,
                        project=settings.vertex_project,
                        daily_budget=ModelDailyBudget(
                            database(),
                            project=settings.vertex_project,
                            model=MODEL,
                            requests=settings.vertex_requests_per_day,
                            tokens=settings.vertex_tokens_per_day,
                        ),
                    )
            except Exception:
                # Explicitly labelled deterministic-Qloo resilience; never fixtures.
                model = None
            app.state.generator = RoundCuratorAgent(
                provider=app.state.qloo,
                model=model,
                capabilities={"artist": ("movie",), "movie": ("artist",)},
            )
        try:
            yield
        finally:
            if model:
                await model.aclose()
            if runtime:
                await runtime.close()
            app.state.qloo = None

    app = FastAPI(
        title="Taste Duel API",
        version="0.2.0-gameplay",
        description="Authoritative sessions/gameplay with awaited fenced generation. Provider use is explicitly configured; browser integration is later work.",
        servers=[
            {"url": "/", "description": "Private API, including the local documentation server"},
            {"url": "/api", "description": "Planned same-origin browser prefix; route paths are /v1"},
        ],
        responses=ERRORS,
        lifespan=lifespan,
    )
    app.state.engine = engine
    app.state.settings = settings
    app.state.generator = generator
    app.add_middleware(BoundedBodyMiddleware)

    def database() -> Engine:
        if app.state.engine is None:
            if settings.database_url is None:
                raise AppError(
                    503, "DATABASE_UNAVAILABLE", "The local database is not configured.", retryable=True
                )
            app.state.engine = local_engine(settings.database_url.get_secret_value())
        return app.state.engine

    def error(request: Request, failure: AppError, fields=()):
        envelope = s.ErrorEnvelope(
            error=s.ErrorPublic(
                code=failure.code,
                message=failure.message,
                retryable=failure.retryable,
                request_id=getattr(request.state, "request_id", uuid4()),
                field_errors=fields,
            )
        )
        return JSONResponse(
            envelope.model_dump(mode="json"),
            status_code=failure.status,
            headers={"Cache-Control": "no-store"},
        )

    @app.middleware("http")
    async def request_boundary(request: Request, call_next):
        request.state.request_id = uuid4()
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if request.headers.get("origin") not in settings.allowed_origins:
                return error(
                    request, AppError(403, "ORIGIN_NOT_ALLOWED", "This request origin is not allowed.")
                )
            length = request.headers.get("content-length", "0")
            if len(length) > 8 or not length.isascii() or not length.isdigit() or int(length) > 16_384:
                return error(request, AppError(413, "REQUEST_TOO_LARGE", "This request is too large."))
        if (
            request.url.path.startswith("/v1/")
            and not request.url.path.startswith("/v1/health/")
            and not (request.method == "DELETE" and request.url.path == "/v1/sessions/current")
            and request.cookies.get(settings.cookie_name)
        ):
            try:
                await asyncio.to_thread(admit_guest_request, request)
            except AppError as failure:
                optional_cookie = (request.method == "POST" and request.url.path == "/v1/sessions") or (
                    request.method == "GET"
                    and re.fullmatch(r"/v1/challenges/[A-Za-z0-9_-]{22,80}", request.url.path) is not None
                )
                if not (failure.status == 401 and optional_cookie):
                    return error(request, failure)
            except SQLAlchemyError:
                return error(
                    request,
                    AppError(
                        503, "DATABASE_UNAVAILABLE", "The service is temporarily unavailable.", retryable=True
                    ),
                )
        try:
            response = await call_next(request)
        except Exception:
            # ServerErrorMiddleware otherwise rethrows after its response, allowing
            # ASGI server exception logging to print arbitrary secret-bearing text.
            # Cancellation remains BaseException and is deliberately propagated.
            return error(
                request,
                AppError(
                    503, "SERVICE_UNAVAILABLE", "The service is temporarily unavailable.", retryable=True
                ),
            )
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Request-ID"] = str(request.state.request_id)
        return response

    @app.exception_handler(AppError)
    async def application_error(request, failure):
        return error(request, failure)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, failure):
        allowed = {
            "body",
            "query",
            "path",
            "header",
            "seed_entity_id",
            "seed_type",
            "mode",
            "round_id",
            "choice_id",
            "expected_revision",
            "answered_round_id",
            "entity_id",
            "game_id",
            "slug",
            "q",
            "type",
            "limit",
            "Idempotency-Key",
        }
        fields = []
        for entry in failure.errors()[:16]:
            loc = tuple(
                part
                if (isinstance(part, int) and 0 <= part <= 10_000)
                or (isinstance(part, str) and part in allowed)
                else "field"
                for part in entry.get("loc", ())[:8]
            )
            kind = entry.get("type", "invalid")
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", kind):
                kind = "invalid"
            fields.append(s.FieldErrorPublic(loc=loc, type=kind))
        return error(request, AppError(422, "INVALID_INPUT", "Check the request fields."), tuple(fields))

    @app.exception_handler(HTTPException)
    async def http_error(request, failure):
        return error(
            request,
            AppError(
                failure.status_code,
                "NOT_FOUND" if failure.status_code == 404 else "REQUEST_FAILED",
                "The requested resource is unavailable.",
            ),
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, _failure):
        return error(
            request,
            AppError(
                503, "DATABASE_UNAVAILABLE", "The local database is temporarily unavailable.", retryable=True
            ),
        )

    @app.exception_handler(ValidationError)
    async def stored_value_error(request, _failure):
        return error(
            request,
            AppError(
                503, "STORED_STATE_UNAVAILABLE", "The saved state is temporarily unavailable.", retryable=True
            ),
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request, _failure):
        return error(
            request,
            AppError(503, "SERVICE_UNAVAILABLE", "The service is temporarily unavailable.", retryable=True),
        )

    def token_parts(request: Request):
        token = request.cookies.get(settings.cookie_name, "")
        try:
            owner, secret = token.split(".", 1)
            if len(secret) != 43 or not re.fullmatch(r"[A-Za-z0-9_-]+", secret):
                raise ValueError
            return UUID(owner), token
        except ValueError:
            raise AppError(401, "SESSION_REQUIRED", "Start a guest session to continue.") from None

    @contextmanager
    def owned_db(request: Request):
        owner, token = token_parts(request)
        # The untrusted UUID selects a possible row; no private data is queried
        # until the full random token hash, expiry and revocation are verified.
        with scoped_session(database(), owner) as db:
            row = db.get(m.Session, owner)
            digest = hashlib.sha256(token.encode()).hexdigest()
            if (
                row is None
                or not hmac.compare_digest(row.token_hash, digest)
                or row.revoked_at is not None
                or row.expires_at <= datetime.now(UTC)
            ):
                raise AppError(401, "SESSION_REQUIRED", "Start a guest session to continue.")
            yield db, row

    def session_public(db, row):
        ids = tuple(
            db.scalars(
                select(m.Game.id)
                .where(
                    m.Game.session_id == row.id,
                    m.Game.expires_at > datetime.now(UTC),
                    m.Game.status.in_(["ready", "playing"]),
                )
                .limit(20)
            )
        )
        return s.SessionPublic(active=True, expires_at=row.expires_at, resumable_game_ids=ids)

    def admit_guest_request(request):
        # Only a verified random guest token determines scope. No IP, forwarding
        # header, fingerprint, search text or personal preference is recorded.
        try:
            with owned_db(request) as (db, row):
                scope = hashlib.sha256(f"guest-admission:{row.id}".encode()).hexdigest()
                path = request.url.path
                if path == "/v1/entities/search":
                    bucket, limit, seconds = "guest-search", settings.guest_searches_per_minute, 60
                elif path == "/v1/games" and request.method == "POST":
                    bucket, limit, seconds = (
                        "guest-generation",
                        settings.guest_generations_per_ten_minutes,
                        600,
                    )
                elif request.method in {"POST", "PUT", "PATCH", "DELETE"}:
                    bucket, limit, seconds = "guest-mutation", settings.guest_mutations_per_minute, 60
                else:
                    bucket, limit, seconds = "guest-read", settings.guest_reads_per_minute, 60
                reserve(db, scope, bucket, limit=limit, seconds=seconds)
        except UsageDenied:
            raise AppError(
                429,
                "SESSION_RATE_LIMITED",
                "Too many requests in this guest session. Wait briefly and retry.",
                retryable=True,
            ) from None

    @app.post(
        "/v1/sessions",
        response_model=s.SessionPublic,
        status_code=201,
        responses={200: {"model": s.SessionPublic}},
        operation_id="createSession",
    )
    def create_session(body: s.SessionCreateRequest, request: Request, response: Response):
        if request.cookies.get(settings.cookie_name):
            try:
                with owned_db(request) as (db, row):
                    response.status_code = 200
                    return session_public(db, row)
            except AppError as failure:
                if failure.status != 401:
                    raise
        owner = uuid4()
        token = f"{owner}.{secrets.token_urlsafe(32)}"
        now = datetime.now(UTC)
        with scoped_session(database(), owner) as db:
            row = m.Session(
                id=owner,
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
                created_at=now,
                expires_at=now + timedelta(seconds=settings.session_ttl_seconds),
            )
            db.add(row)
            db.flush()
            result = s.SessionPublic(active=True, expires_at=row.expires_at)
        response.set_cookie(
            settings.cookie_name,
            token,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="lax",
            path="/",
            max_age=settings.session_ttl_seconds,
        )
        return result

    @app.get("/v1/sessions/current", response_model=s.SessionPublic, operation_id="getCurrentSession")
    def current_session(request: Request):
        with owned_db(request) as (db, row):
            return session_public(db, row)

    @app.delete("/v1/sessions/current", status_code=204, operation_id="clearSession")
    def clear_session(request: Request):
        try:
            with owned_db(request) as (db, row):
                # Match mutation/publication lock order: session first.
                db.refresh(row, with_for_update=True)
                now = datetime.now(UTC)
                if row.revoked_at is not None or row.expires_at <= now:
                    raise AppError(401, "SESSION_REQUIRED", "Start a guest session to continue.")
                db.execute(
                    update(m.Challenge)
                    .where(m.Challenge.session_id == row.id, m.Challenge.revoked_at.is_(None))
                    .values(revoked_at=now)
                )
                db.execute(
                    update(m.GenerationReservation)
                    .where(
                        m.GenerationReservation.session_id == row.id,
                        m.GenerationReservation.status.in_(["reserved", "running"]),
                    )
                    .values(status="cancelled", lease_owner=None, lease_expires_at=None)
                )
                row.revoked_at = now
        except AppError as failure:
            if failure.status != 401:
                raise
        response = Response(status_code=204)
        response.delete_cookie(
            settings.cookie_name, path="/", httponly=True, secure=settings.cookie_secure, samesite="lax"
        )
        return response

    def not_implemented():
        raise AppError(
            501,
            "FOUNDATION_NOT_IMPLEMENTED",
            "This operation is defined but not connected in the foundation stage.",
        )

    @app.get("/v1/entities/search", response_model=s.EntitySearchPublic, operation_id="searchEntities")
    async def search_entities(
        request: Request,
        q: Annotated[str, Query(min_length=1, max_length=100)],
        type: EntityType,
        limit: Annotated[int, Query(ge=1, le=20)] = 10,
    ):
        with owned_db(request) as (_, row):
            owner = row.id
        port = getattr(app.state, "qloo", None)
        if port is None:
            raise AppError(503, "QLOO_UNAVAILABLE", "Entity search is not configured.", retryable=True)
        async with port.request_budget(max_requests=2, deadline_seconds=8):
            result = await port.resolve_seed(ResolveSeedRequest(q, type))
        if result.error:
            raise AppError(
                503, "QLOO_UNAVAILABLE", "Entity search is temporarily unavailable.", retryable=True
            )
        items = result.entities or tuple(choice for issue in result.issues for choice in issue.choices)
        unique = {item.id: item for item in items}
        stored, expired = await asyncio.to_thread(
            remember_search_entities, database(), owner, tuple(unique.values())[:limit]
        )
        status = (
            result.status if result.status in ("ok", "empty", "needs_input", "partial") else "unavailable"
        )
        return s.EntitySearchPublic(
            status="unavailable" if expired and not stored else status,
            results=tuple(presenters.entity(item) for item in stored),
            message="This session's saved seed has expired. Start a new guest session."
            if expired
            else "Choose the intended entity."
            if status == "needs_input"
            else None,
        )

    @app.post(
        "/v1/games",
        response_model=s.GamePublic,
        status_code=201,
        responses={200: {"model": s.GamePublic}, 202: {"model": s.GameGenerationPendingPublic}},
        operation_id="createGame",
    )
    async def create_game(
        body: s.CreateGameRequest, request: Request, response: Response, idempotency_key: Key
    ):
        # Authenticate in a short transaction; hold no database lock across I/O.
        with owned_db(request) as (_, row):
            owner = row.id
        service = GameplayService(database())
        claim = await asyncio.to_thread(
            service.reserve, owner, **body.model_dump(), idempotency_key=idempotency_key
        )
        if isinstance(claim, GenerationObservation):
            if claim.status == "succeeded":
                response.status_code = 200
                return read_game(request, claim.game_id)
            response.status_code = 202
            seconds = max(1, min(30, int((claim.lease_expires_at - datetime.now(UTC)).total_seconds()) + 1))
            response.headers["Retry-After"] = str(seconds)
            return JSONResponse(
                s.GameGenerationPendingPublic(
                    game_id=claim.game_id,
                    retry_after_seconds=seconds,
                    lease_expires_at=claim.lease_expires_at,
                ).model_dump(mode="json"),
                status_code=202,
                headers={"Retry-After": str(seconds), "Cache-Control": "no-store"},
            )
        try:
            curator = app.state.generator
            if curator is None:
                raise AppError(
                    503,
                    "GENERATION_UNAVAILABLE",
                    "Generation is not configured. Retry this request when available.",
                    retryable=True,
                )
            async with asyncio.timeout(20):
                outcome = await curator.curate(
                    claim.seed, game_id=claim.game_id, rng_seed=secrets.token_hex(32), allow_fallback=True
                )
            if outcome.pool is None:
                raise AppError(
                    503,
                    "GENERATION_UNAVAILABLE",
                    "A verified five-round game could not be prepared. Retry or choose another seed.",
                    retryable=True,
                )
            if generator is None and outcome.receipt.curator_mode == "fixture":
                raise AppError(
                    503, "GENERATION_UNAVAILABLE", "Synthetic evidence is not enabled in this runtime."
                )
            await asyncio.to_thread(service.publish, claim, outcome)
        except asyncio.CancelledError:
            # An interrupted request leaves an expiring claim; no detached work.
            raise
        except Exception as failure:
            try:
                await asyncio.to_thread(service.fail, claim)
            except (AppError, SQLAlchemyError):
                pass  # Expired/reclaimed/revoked claims must never overwrite a winner.
            if isinstance(failure, (AppError, SQLAlchemyError, ValidationError)):
                raise
            raise AppError(
                503,
                "GENERATION_UNAVAILABLE",
                "Generation was interrupted. Retry the same request.",
                retryable=True,
            ) from None
        return read_game(request, claim.game_id)

    def read_game(request, game_id):
        with owned_db(request) as (db, row):
            return presenters.game_public(ReadService(SqlReadRepository(db, row.id), row.id).game(game_id))

    @app.get(
        "/v1/games/{game_id}/generation",
        response_model=s.GenerationStatusPublic,
        operation_id="getGenerationStatus",
    )
    def generation_status(game_id: UUID, request: Request):
        with owned_db(request) as (_, row):
            owner = row.id
        observation = GameplayService(database()).status(owner, game_id)
        if observation is None:
            raise AppError(404, "NOT_FOUND", "The requested resource is unavailable.")
        now = datetime.now(UTC)
        running = (
            observation.status == "running"
            and observation.lease_expires_at
            and observation.lease_expires_at > now
        )
        state = (
            "generation_in_progress"
            if running
            else (
                "retryable"
                if observation.status in ("running", "reserved", "failed")
                else "failed"
                if observation.status == "exhausted"
                else observation.status
            )
        )
        return s.GenerationStatusPublic(
            game_id=game_id,
            status=state,
            lease_expires_at=observation.lease_expires_at,
            retry_after_seconds=max(1, min(30, int((observation.lease_expires_at - now).total_seconds()) + 1))
            if running
            else None,
            recovery_action="wait_then_retry"
            if running
            else (
                "read_game"
                if state == "succeeded"
                else "retry_same_request"
                if state == "retryable"
                else "start_new_game"
            ),
        )

    @app.get("/v1/games/{game_id}", response_model=s.GamePublic, operation_id="getGame")
    def get_game(game_id: UUID, request: Request):
        return read_game(request, game_id)

    @app.get(
        "/v1/games/{game_id}/round", response_model=s.PlayableRoundPublic, operation_id="getCurrentRound"
    )
    def get_round(game_id: UUID, request: Request):
        with owned_db(request) as (db, row):
            return presenters.round_public(
                ReadService(SqlReadRepository(db, row.id), row.id).playable(game_id)
            )

    @app.post("/v1/games/{game_id}/answer", response_model=s.RevealedRoundPublic, operation_id="answerRound")
    def answer(game_id: UUID, body: s.AnswerRequest, request: Request, idempotency_key: Key):
        with owned_db(request) as (_, row):
            owner = row.id
        result = GameplayService(database()).answer(
            owner, game_id, **body.model_dump(), idempotency_key=idempotency_key
        )
        return mutation_public(request, result, answer=True)

    @app.post("/v1/games/{game_id}/advance", response_model=s.GamePublic, operation_id="advanceRound")
    def advance(game_id: UUID, body: s.AdvanceRequest, request: Request, idempotency_key: Key):
        with owned_db(request) as (_, row):
            owner = row.id
        result = GameplayService(database()).advance(
            owner, game_id, **body.model_dump(), idempotency_key=idempotency_key
        )
        return mutation_public(request, result, answer=False, final=body.answered_round_id == result.round_id)

    def mutation_public(request, result, *, answer, final=False):
        """Rebuild the saved mutation revision, never today's later navigation state."""
        with owned_db(request) as (db, row):
            repo = SqlReadRepository(db, row.id)
            game = ReadService(repo, row.id).game(result.game_id)
            delivered = db.scalar(
                select(m.DeliveredRound).where(
                    m.DeliveredRound.id == result.round_id,
                    m.DeliveredRound.session_id == row.id,
                    m.DeliveredRound.game_id == result.game_id,
                )
            )
            if delivered is None:
                raise AppError(404, "NOT_FOUND", "The requested resource is unavailable.")
            saved_round = repo.round(result.game_id, delivered, game.seed.source)
            if answer or final:
                if saved_round.accepted is None:
                    raise AppError(503, "STORED_STATE_UNAVAILABLE", "The saved answer is unavailable.")
                count = saved_round.ordinal
                score = saved_round.accepted.cumulative_score
            else:
                count = saved_round.ordinal - 1
                score = sum(
                    db.scalars(
                        select(m.Answer.correct)
                        .join(m.DeliveredRound, m.DeliveredRound.id == m.Answer.round_id)
                        .where(
                            m.Answer.session_id == row.id,
                            m.Answer.game_id == game.id,
                            m.DeliveredRound.ordinal < saved_round.ordinal,
                        )
                    )
                )
                saved_round = replace(saved_round, accepted=None)
            snapshot = replace(
                game,
                revision=result.revision,
                current=saved_round,
                current_ordinal=saved_round.ordinal,
                answered_count=count,
                score=score,
                phase="completed" if count == 5 else "playing",
            )
            return presenters.round_public(snapshot) if answer else presenters.game_public(snapshot)

    @app.get("/v1/games/{game_id}/results", response_model=s.GameResultPublic, operation_id="getResults")
    def results(game_id: UUID, request: Request):
        with owned_db(request) as (db, row):
            repo = SqlReadRepository(db, row.id)
            game, rounds = ReadService(repo, row.id).results(game_id)
            return s.GameResultPublic(
                game_id=game.id,
                mode=game.mode,
                score=game.score,
                source=game.seed.source,
                curator_mode=game.receipt.curator_mode,
                answered_rounds=tuple(presenters.round_public(game, r) for r in rounds),
                discoveries=tuple(presenters.discovery_public(d) for d in repo.discoveries()),
                expires_at=game.expires_at,
            )

    @app.get("/v1/discoveries", response_model=s.DiscoveriesPublic, operation_id="getDiscoveries")
    def discoveries(request: Request):
        with owned_db(request) as (db, row):
            items, expired = SqlReadRepository(db, row.id).discovery_collection()
            return s.DiscoveriesPublic(
                discoveries=tuple(presenters.discovery_public(d) for d in items),
                expired_count=expired,
                session_expires_at=row.expires_at,
            )

    @app.post(
        "/v1/discoveries",
        response_model=s.DiscoveryPublic,
        status_code=201,
        responses={200: {"model": s.DiscoveryPublic}},
        operation_id="saveDiscovery",
    )
    def save_discovery(
        body: s.DiscoveryCreateRequest, request: Request, response: Response, idempotency_key: Key
    ):
        with owned_db(request) as (_, row):
            owner = row.id
        result = DiscoveryService(database()).save(owner, body.entity_id, idempotency_key)
        response.status_code = 201 if result.created else 200
        with owned_db(request) as (db, row):
            saved = next(
                (
                    item
                    for item in SqlReadRepository(db, row.id).discoveries()
                    if item.entity.id == result.entity_id
                ),
                None,
            )
            if saved is None:
                raise AppError(410, "DISCOVERY_EXPIRED", "This discovery is no longer available.")
            return presenters.discovery_public(saved)

    @app.delete("/v1/discoveries/{entity_id}", status_code=204, operation_id="removeDiscovery")
    def remove_discovery(entity_id: UUID, request: Request):
        with owned_db(request) as (_, row):
            owner = row.id
        DiscoveryService(database()).remove(owner, entity_id)
        return Response(status_code=204)

    def challenge_invitation(slug):
        challenge, seed = ChallengeService(database()).invitation(slug)
        source = "fixture" if seed.provider == "fixture" else "qloo"
        return s.ChallengeInvitationPublic(
            slug=slug,
            seed=s.EntityPublic(id=seed.id, name=seed.name, type=seed.entity_type, source=source),
            creator_score=challenge.creator_score,
            source=source,
            expires_at=challenge.expires_at,
        )

    @app.post(
        "/v1/challenges",
        response_model=s.ChallengeCreatedPublic,
        status_code=201,
        responses={200: {"model": s.ChallengeCreatedPublic}},
        operation_id="createChallenge",
    )
    def create_challenge(
        body: s.ChallengeCreateRequest, request: Request, response: Response, idempotency_key: Key
    ):
        with owned_db(request) as (_, row):
            owner = row.id
        slug, created = ChallengeService(database()).create(owner, body.game_id, idempotency_key)
        response.status_code = 201 if created else 200
        return s.ChallengeCreatedPublic(invitation=challenge_invitation(slug), share_path=f"/c/{slug}")

    @app.get(
        "/v1/challenges/{slug}",
        response_model=s.ChallengeInvitationPublic,
        operation_id="getChallengeInvitation",
    )
    def invitation(slug: Annotated[str, Path(min_length=22, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")]):
        return challenge_invitation(slug)

    @app.delete("/v1/challenges/{slug}", status_code=204, operation_id="revokeChallenge")
    def revoke_challenge(
        slug: Annotated[str, Path(min_length=22, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")],
        request: Request,
    ):
        with owned_db(request) as (_, row):
            owner = row.id
        ChallengeService(database()).revoke(owner, slug)
        return Response(status_code=204)

    @app.post(
        "/v1/challenges/{slug}/plays",
        response_model=s.GamePublic,
        status_code=201,
        responses={200: {"model": s.GamePublic}},
        operation_id="playChallenge",
    )
    def play_challenge(
        slug: Annotated[str, Path(min_length=22, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")],
        body: s.ChallengePlayRequest,
        request: Request,
        response: Response,
        idempotency_key: Key,
    ):
        with owned_db(request) as (_, row):
            owner = row.id
        game_id, created = ChallengeService(database()).play(owner, slug, idempotency_key)
        response.status_code = 201 if created else 200
        return read_game(request, game_id)

    @app.get("/v1/health/live", response_model=s.HealthPublic, operation_id="liveness")
    def live():
        return s.HealthPublic(status="ok")

    @app.get("/v1/health/ready", response_model=s.HealthPublic, operation_id="readiness")
    def ready():
        with database().connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM tasteduel.tasteduel_alembic_version LIMIT 1")
            ).scalar_one()
            if revision != "td0009":
                raise AppError(503, "SCHEMA_NOT_READY", "The local schema is not ready.", retryable=True)
        return s.HealthPublic(status="ok", generation_available=app.state.generator is not None)

    return app


app = create_app()
