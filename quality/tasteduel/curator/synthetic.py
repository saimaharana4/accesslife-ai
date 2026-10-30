"""Typed synthetic doubles, not Qloo or Vertex evidence."""

import asyncio
from collections import deque
from datetime import UTC, datetime
from uuid import UUID

from tasteduel.adapters.qloo_policy import AdmissionDenied, GuardedQlooPort
from tasteduel.ports.curator import ModelTurn, ToolCall
from tasteduel.ports.qloo import (
    EntityMetadata,
    ProviderFailure,
    QlooResult,
    RankedCandidate,
    RankingEvidence,
    ranked_context_hash,
)

SEED = EntityMetadata(UUID(int=999), "Synthetic seed, not a live artist", "artist")
GAME_ID = UUID(int=998)


class SyntheticAdmission:
    def __init__(self):
        self.admitted = 0
        self.recorded = []
        self.denied = None

    async def admit(self, scope):
        if self.denied:
            raise AdmissionDenied(self.denied)
        self.admitted += 1

    async def record(self, scope, *, failed, auth=False):
        self.recorded.append((failed, auth))
        if auth:
            self.denied = "QLOO_AUTHENTICATION_FAILED"


class SyntheticRankedProvider:
    """Every mocked internal GET still crosses the real request guard."""

    def __init__(self, *, counts=(), paths=("/v2/insights",), delay=0, failure=None, mutate=None):
        self.counts = deque(counts)
        self.paths, self.delay, self.failure, self.mutate = paths, delay, failure, mutate
        self.requests = []
        self.dispatched = []
        self.guard = None
        self.cancelled = False

    async def resolve_seed(self, request):
        raise AssertionError("Confirmed seed must not be re-resolved or guessed")

    async def ranked_candidates(self, request):
        self.requests.append(request)
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            for path in self.paths:
                try:
                    await self.guard.reserve_upstream(path)
                except AdmissionDenied as denied:
                    return QlooResult("error", error=ProviderFailure(denied.code))
                self.guard.note_dispatch(path)
                self.dispatched.append(path)
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        if self.failure:
            return QlooResult("error", error=self.failure)
        count = self.counts.popleft() if self.counts else request.limit
        result = QlooResult(
            "ok",
            candidates=tuple(
                RankedCandidate(
                    EntityMetadata(
                        UUID(int=(1000 if request.target_domain == "movie" else 2000) + index),
                        f"Synthetic {request.target_domain} contestant {index}",
                        request.target_domain,
                    ),
                    float(100 - 4 * index),
                    index,
                )
                for index in range(count)
            ),
            evidence=RankingEvidence(
                ranked_context_hash(request),
                datetime.now(UTC),
                score_field="query.affinity",
                ordering_verified=True,
            ),
        )
        return self.mutate(result) if self.mutate else result


def provider(**kwargs):
    inner, admission = SyntheticRankedProvider(**kwargs), SyntheticAdmission()
    guard = GuardedQlooPort(inner, admission, "c" * 64)
    inner.guard = guard
    return guard, inner, admission


def call(name, **arguments):
    return ModelTurn((ToolCall(name, arguments),), input_tokens=60, output_tokens=20)


def latest_snapshot(messages):
    """Find only the opaque handle supplied by the application tool response."""

    def find(value):
        if isinstance(value, dict):
            if "snapshot_id" in value and value["snapshot_id"]:
                return value["snapshot_id"]
            for child in reversed(tuple(value.values())):
                if result := find(child):
                    return result
        elif isinstance(value, (tuple, list)):
            for child in reversed(value):
                if result := find(child):
                    return result
        return None

    return find(messages)


class ScriptedModel:
    model_version = "synthetic-model-no-network"

    def __init__(self, *turns):
        self.turns = deque(turns)
        self.observed = []

    async def decide(self, messages, available_tools, *, timeout_seconds):
        self.observed.append((messages, available_tools, timeout_seconds))
        if not self.turns:
            raise AssertionError("Unexpected extra model request")
        turn = self.turns.popleft()
        if isinstance(turn, Exception):
            raise turn
        if callable(turn):
            turn = turn(messages)
        if hasattr(turn, "__await__"):
            turn = await turn
        return turn


def finish(messages):
    handle = latest_snapshot(messages)
    assert handle, "Application tool response must provide a known opaque snapshot handle"
    return call("finish_pool", snapshot_id=handle)
