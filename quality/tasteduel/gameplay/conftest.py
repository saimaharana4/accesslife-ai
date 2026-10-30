"""Synthetic, project-owned generation with real deterministic pool validation."""

import asyncio
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
import hashlib
from threading import Event, Lock
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest

from tasteduel.agents.round_curator import CuratorOutcome
from tasteduel.api.main import create_app
from tasteduel.application.pool_preparation import PreparedPool
from tasteduel.config import Settings
from tasteduel.domain.curation import CurationAction, CurationReceipt
from tasteduel.domain.duel_pool import Candidate, RankingSnapshot, build_pool
from tasteduel.domain.pool_feedback import feedback_from_pool
from tasteduel.persistence import models as m
from tasteduel.persistence.db import scoped_session


class SyntheticCurator:
    """Test-only seam. It calls no provider and cannot claim Qloo evidence."""

    def __init__(self, *, block_first=False):
        self.calls = 0
        self.lock = Lock()
        self.started = Event()
        self.release = Event()
        self.block_first = block_first
        self.outcomes = []
        self.execution_id = uuid4().hex

    async def curate(self, seed, *, game_id, rng_seed, allow_fallback=True):
        with self.lock:
            self.calls += 1
            call = self.calls
        self.started.set()
        if self.block_first and call == 1:
            if not await asyncio.to_thread(self.release.wait, 15):
                raise RuntimeError("Synthetic test release deadline exceeded")
        context = hashlib.sha256(f"owned-fixture:{seed.id}:{call}".encode()).hexdigest()
        candidates = tuple(
            Candidate(
                id=UUID(int=100_000 + index),
                name=f"SYNTHETIC_PRIVATE_MOVIE_{index:02d}",
                domain="movie",
                affinity=float(200 - index * 7),
                position=index + 1,
                context_hash=context,
            )
            for index in range(20)
        )
        snapshot = RankingSnapshot(
            context, "movie", seed.id, seed.domain, candidates, True, provider="fixture"
        )
        pool = build_pool(snapshot, rng_seed=rng_seed)
        assert pool.status == "ready" and len(pool.path) == 5
        feedback = feedback_from_pool(pool)
        receipt = CurationReceipt(
            game_id=game_id,
            curator_mode="fixture",
            seed_entity_id=seed.id,
            seed_type=seed.domain,
            target_domains_considered=("movie",),
            target_domains_selected=("movie",),
            qloo_request_count=0,
            tool_request_count=0,
            model_request_count=0,
            candidate_count_received=20,
            rejection_counts={},
            valid_pair_count=len(pool.pairs),
            bounded_correction_count=0,
            five_round_path_verified=True,
            provider_version=f"fixture-{self.execution_id}-{call}",
            validator_version=pool.policy.version,
            elapsed_ms=call,
            action_trace=(CurationAction(tool="finish_pool", status="ok", elapsed_ms=call),),
            policy_fingerprint=pool.policy.fingerprint,
            final_pool_status="ready",
            final_feedback=feedback,
            evaluation_feedback=(feedback,),
            final_target_domain="movie",
            status="succeeded",
            created_at=datetime.now(UTC),
        )
        outcome = CuratorOutcome(
            PreparedPool(
                feedback, pool, snapshot, receipt.created_at, receipt.created_at + timedelta(hours=1)
            ),
            receipt,
            (),
        )
        self.outcomes.append(outcome)
        return outcome


@pytest.fixture
def gameplay(db_engine):
    with ExitStack() as stack:

        def make(*, generator=None, cookie=None):
            generator = generator or SyntheticCurator()
            app = create_app(
                Settings(cookie_secure=True, allowed_origins=("https://testserver",)),
                engine=db_engine,
                generator=generator,
            )
            client = stack.enter_context(
                TestClient(
                    app,
                    base_url="https://testserver",
                    headers={"Origin": "https://testserver"},
                    raise_server_exceptions=False,
                )
            )
            if cookie:
                client.cookies.set("tasteduel_session", cookie)
                owner = UUID(cookie.split(".", 1)[0])
                return client, owner, generator
            assert client.post("/v1/sessions", json={}).status_code == 201
            owner = UUID(client.cookies.get("tasteduel_session").split(".", 1)[0])
            return client, owner, generator

        yield make


@pytest.fixture
def owned_seed(db_engine):
    def make(owner):
        identifier = uuid4()
        with scoped_session(db_engine, owner) as db:
            db.add(
                m.Entity(
                    id=identifier,
                    session_id=owner,
                    entity_type="artist",
                    name="Synthetic Gameplay Seed",
                    provider="fixture",
                    provider_entity_id=str(identifier),
                    attribution="Project-owned synthetic gameplay test data",
                    rights_policy="project_owned",
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                )
            )
        return {"seed_entity_id": str(identifier), "seed_type": "artist", "mode": "solo"}

    return make
