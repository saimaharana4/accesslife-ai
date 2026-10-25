"""Taste Duel contract/read foundation. No provider calls or gameplay mutations.

Run separately from accesslife.api.main; no automatic migration or import I/O.
"""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
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
from tasteduel.api import presenters, schemas as s
from tasteduel.api.body_limit import BoundedBodyMiddleware
from tasteduel.application.errors import AppError
from tasteduel.application.reads import ReadService
from tasteduel.config import Settings
from tasteduel.domain.types import EntityType
from tasteduel.persistence import models as m
from tasteduel.persistence.db import local_engine, scoped_session

Key = Annotated[
    str, Header(alias="Idempotency-Key", min_length=16, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
]
ERRORS = {code: {"model": s.ErrorEnvelope} for code in (401, 403, 404, 409, 410, 413, 422, 429, 501, 503)}


def create_app(settings: Settings | None = None, *, engine: Engine | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(
        title="Taste Duel API",
        version="0.1.0-foundation",
        description="Prompt 5 contract and owned-read foundation. Live search, generation and mutations are not connected.",
        servers=[
            {"url": "/", "description": "Private API, including the local documentation server"},
            {"url": "/api", "description": "Planned same-origin browser prefix; route paths are /v1"},
        ],
        responses=ERRORS,
    )
    app.state.engine = engine
    app.state.settings = settings
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
            if not length.isdigit() or int(length) > 16_384:
                return error(request, AppError(413, "REQUEST_TOO_LARGE", "This request is too large."))
        response = await call_next(request)
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
                now = datetime.now(UTC)
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
    def search_entities(
        request: Request,
        q: Annotated[str, Query(min_length=1, max_length=100)],
        type: EntityType,
        limit: Annotated[int, Query(ge=1, le=20)] = 10,
    ):
        with owned_db(request):
            not_implemented()

    @app.post(
        "/v1/games",
        response_model=s.GamePublic,
        status_code=201,
        responses={200: {"model": s.GamePublic}, 202: {"model": s.GameGenerationPendingPublic}},
        operation_id="createGame",
    )
    def create_game(body: s.CreateGameRequest, request: Request, idempotency_key: Key):
        with owned_db(request):
            not_implemented()

    @app.get("/v1/games/{game_id}", response_model=s.GamePublic, operation_id="getGame")
    def get_game(game_id: UUID, request: Request):
        with owned_db(request) as (db, row):
            return presenters.game_public(ReadService(SqlReadRepository(db, row.id), row.id).game(game_id))

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
        with owned_db(request):
            not_implemented()

    @app.post("/v1/games/{game_id}/advance", response_model=s.GamePublic, operation_id="advanceRound")
    def advance(game_id: UUID, body: s.AdvanceRequest, request: Request, idempotency_key: Key):
        with owned_db(request):
            not_implemented()

    @app.get("/v1/games/{game_id}/results", response_model=s.GameResultPublic, operation_id="getResults")
    def results(game_id: UUID, request: Request):
        with owned_db(request) as (db, row):
            repo = SqlReadRepository(db, row.id)
            game, rounds = ReadService(repo, row.id).results(game_id)
            return s.GameResultPublic(
                game_id=game.id,
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
            return s.DiscoveriesPublic(
                discoveries=tuple(
                    presenters.discovery_public(d) for d in SqlReadRepository(db, row.id).discoveries()
                )
            )

    @app.post(
        "/v1/discoveries",
        response_model=s.DiscoveryPublic,
        status_code=201,
        responses={200: {"model": s.DiscoveryPublic}},
        operation_id="saveDiscovery",
    )
    def save_discovery(body: s.DiscoveryCreateRequest, request: Request, idempotency_key: Key):
        with owned_db(request):
            not_implemented()

    @app.delete("/v1/discoveries/{entity_id}", status_code=204, operation_id="removeDiscovery")
    def remove_discovery(entity_id: UUID, request: Request):
        with owned_db(request):
            not_implemented()

    @app.post(
        "/v1/challenges",
        response_model=s.ChallengeCreatedPublic,
        status_code=201,
        responses={200: {"model": s.ChallengeCreatedPublic}},
        operation_id="createChallenge",
    )
    def create_challenge(body: s.ChallengeCreateRequest, request: Request, idempotency_key: Key):
        with owned_db(request):
            not_implemented()

    @app.get(
        "/v1/challenges/{slug}",
        response_model=s.ChallengeInvitationPublic,
        operation_id="getChallengeInvitation",
    )
    def invitation(slug: Annotated[str, Path(min_length=22, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")]):
        not_implemented()

    @app.post(
        "/v1/challenges/{slug}/plays",
        response_model=s.GamePublic,
        status_code=201,
        responses={200: {"model": s.GamePublic}},
        operation_id="playChallenge",
    )
    def play_challenge(
        slug: Annotated[str, Path(min_length=22, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")],
        request: Request,
        idempotency_key: Key,
    ):
        with owned_db(request):
            not_implemented()

    @app.get("/v1/health/live", response_model=s.HealthPublic, operation_id="liveness")
    def live():
        return s.HealthPublic(status="ok")

    @app.get("/v1/health/ready", response_model=s.HealthPublic, operation_id="readiness")
    def ready():
        with database().connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM tasteduel.tasteduel_alembic_version LIMIT 1")
            ).scalar_one()
            if revision != "td0004":
                raise AppError(503, "SCHEMA_NOT_READY", "The local schema is not ready.", retryable=True)
        return s.HealthPublic(status="ok", generation_available=False)

    return app


app = create_app()
