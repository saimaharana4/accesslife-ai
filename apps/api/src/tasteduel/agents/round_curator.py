"""Bounded model-selected curation; model output never changes deterministic evidence."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
import json
import math
import time
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError

from tasteduel.agents.curator_tools import tool_schemas
from tasteduel.application.pool_preparation import PreparedPool, prepare_qloo_pool
from tasteduel.domain.curation import CurationAction, CurationReceipt
from tasteduel.domain.duel_pool import PairQualityPolicy
from tasteduel.domain.types import CuratorMode, GenerationStatus
from tasteduel.ports.curator import CuratorModel, ModelTurn, ModelUnavailable, ToolCall
from tasteduel.ports.qloo import EntityMetadata, RankedCandidatesRequest


@dataclass(frozen=True)
class CuratorLimits:
    overall_seconds: float = 20
    max_qloo_requests: int = 6
    max_model_requests: int = 4
    max_tool_steps: int = 8
    max_total_tokens: int = 24000
    max_output_tokens: int = 512
    max_corrections: int = 1

    def __post_init__(self):
        if not math.isfinite(self.overall_seconds) or not 0 < self.overall_seconds <= 20:
            raise ValueError("Invalid overall deadline")
        for value, ceiling in (
            (self.max_qloo_requests, 6),
            (self.max_model_requests, 4),
            (self.max_tool_steps, 8),
            (self.max_total_tokens, 24000),
            (self.max_output_tokens, 512),
        ):
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError("Invalid curator budget")
        if type(self.max_corrections) is not int or self.max_corrections not in (0, 1):
            raise ValueError("Invalid correction budget")


@dataclass(frozen=True)
class ActionFact:
    action: str
    status: Literal["ok", "rejected", "error", "timeout"]
    elapsed_ms: int
    target_domain: Literal["artist", "movie"] | None = None
    candidate_limit: int | None = None


@dataclass(frozen=True)
class CuratorOutcome:
    prepared: PreparedPool | None
    receipt: CurationReceipt
    trace: tuple[ActionFact, ...]
    failure_code: str | None = None

    @property
    def pool(self):
        return (
            self.prepared.pool
            if self.prepared and self.receipt.status == GenerationStatus.SUCCEEDED
            else None
        )


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class _Fetch(_Args):
    target_domain: Literal["artist", "movie"]
    limit: StrictInt = Field(ge=10, le=20)


class _Snapshot(_Args):
    snapshot_id: str = Field(pattern=r"^[0-9a-f-]{36}$")


class _Stop(_Args):
    reason: Literal["insufficient_coverage", "provider_unavailable", "budget_exhausted"]


class _Halt(Exception):
    def __init__(self, code):
        self.code = code


class RoundCuratorAgent:
    """The caller supplies verified capabilities, never model-discovered support.

    `provider` must enforce actual HTTP reservations using its request_budget context.
    No provider/SDK details, entity names, images, scores, pairs or winners enter the model.
    """

    def __init__(
        self,
        *,
        provider,
        model: CuratorModel | None,
        capabilities: dict,
        limits: CuratorLimits = CuratorLimits(),
        policy: PairQualityPolicy = PairQualityPolicy(),
    ):
        if any(
            key not in ("artist", "movie")
            or not values
            or len(set(values)) != len(values)
            or any(value not in ("artist", "movie") for value in values)
            for key, values in capabilities.items()
        ):
            raise ValueError("Capabilities must be verified supported domains")
        self.provider, self.model = provider, model
        self.capabilities = {key: tuple(values) for key, values in capabilities.items()}
        self.limits, self.policy = limits, policy

    async def curate(
        self,
        seed: EntityMetadata,
        *,
        game_id: UUID,
        rng_seed: str,
        now: datetime | None = None,
        allow_fallback: bool = True,
    ) -> CuratorOutcome:
        started = time.monotonic()
        now_override = now
        now = now or datetime.now(UTC)
        if not isinstance(seed.id, UUID) or seed.domain not in ("artist", "movie"):
            raise ValueError("A confirmed typed seed is required")
        domains = self.capabilities.get(seed.domain, ())
        if not domains:
            raise ValueError("No verified target domain for this seed type")
        run = _Run(self, seed, game_id, rng_seed, now, started, domains, now_override)
        try:
            async with asyncio.timeout(self.limits.overall_seconds):
                async with self.provider.request_budget(
                    max_requests=self.limits.max_qloo_requests,
                    deadline_seconds=self.limits.overall_seconds,
                ) as budget:
                    run.budget = budget
                    if self.model is None:
                        if not allow_fallback:
                            raise _Halt("MODEL_UNAVAILABLE")
                        await run.fallback()
                    else:
                        try:
                            await run.loop()
                        except ModelUnavailable:
                            if not allow_fallback:
                                raise _Halt("MODEL_UNAVAILABLE") from None
                            await run.fallback()
        except _Halt as failure:
            run.failure = failure.code
            # A model formatting/tool mistake must not discard verified evidence.
            # Never fetch again here or recover auth, deadline, budget or veto failures.
            if (
                allow_fallback
                and failure.code in {
                    "MALFORMED_MODEL_OUTPUT", "MALFORMED_TOOL_ARGUMENTS", "UNSUPPORTED_TOOL",
                    "REPEATED_TOOL_CALL", "UNKNOWN_SNAPSHOT", "UNNECESSARY_CORRECTION",
                }
                and run.current and run.current.pool and run.current.pool.path
                and run.current.feedback.status == "ready" and run.remaining() > 0
            ):
                await run.fallback()
                run.failure = None
        except TimeoutError:
            run.failure = "CURATION_DEADLINE"
            run.fact("model_request", "timeout", started)
        # Cancellation deliberately propagates: no delayed fallback may publish after cancellation.
        return run.outcome()


class _Run:
    def __init__(self, agent, seed, game_id, rng_seed, now, started, domains, now_override):
        self.agent, self.seed, self.game_id, self.rng_seed = agent, seed, game_id, rng_seed
        self.now, self.started, self.domains = now, started, domains
        self.now_override = now_override
        self.messages = [
            {
                "role": "user",
                "data": {
                    "confirmed_seed": {"id": str(seed.id), "domain": seed.domain},
                    "verified_target_domains": list(domains),
                    "maximum_corrections": agent.limits.max_corrections,
                    "remaining_qloo_http_requests": agent.limits.max_qloo_requests,
                },
            }
        ]
        self.budget = None
        self.models = self.steps = self.tokens = self.corrections = self.received = 0
        self.input_tokens = self.output_tokens = 0
        self.rejected = 0
        self.usage_complete = True
        self.trace, self.snapshots, self.strategies, self.signatures = [], {}, [], set()
        self.selected = None
        self.current = None
        self.failure = None
        self.mode = CuratorMode.GENUINE_AGENT

    def remaining(self):
        return max(0, self.agent.limits.overall_seconds - (time.monotonic() - self.started))

    def fact(self, action, status, started, *, target_domain=None, candidate_limit=None):
        self.trace.append(
            ActionFact(
                action,
                status,
                max(0, int((time.monotonic() - started) * 1000)),
                target_domain,
                candidate_limit,
            )
        )

    async def loop(self):
        while self.models < self.agent.limits.max_model_requests:
            upper_bound = getattr(self.agent.model, "input_token_upper_bound", None)
            reserved_tokens = (
                upper_bound(tuple(self.messages), tool_schemas(self.domains))
                + self.agent.limits.max_output_tokens
                if upper_bound
                else self.agent.limits.max_output_tokens
            )
            if self.tokens + reserved_tokens > self.agent.limits.max_total_tokens:
                raise _Halt("MODEL_TOKEN_BUDGET")
            started = time.monotonic()
            self.models += 1  # Attempts, including failed calls, are execution facts.
            try:
                turn = await self.agent.model.decide(
                    tuple(self.messages), tool_schemas(self.domains), timeout_seconds=self.remaining()
                )
            except ModelUnavailable:
                self.usage_complete = False
                self.fact("model_request", "error", started)
                raise
            except asyncio.CancelledError:
                self.usage_complete = False
                self.fact("model_request", "timeout", started)
                raise
            self.fact("model_request", "ok", started)
            if (
                not isinstance(turn, ModelTurn)
                or not isinstance(turn.calls, tuple)
                or not 1 <= len(turn.calls) <= 3
            ):
                self.usage_complete = False
                raise _Halt("MALFORMED_MODEL_OUTPUT")
            if (
                any(type(value) is not int or value < 0 for value in (turn.input_tokens, turn.output_tokens))
                or turn.input_tokens > 32000
                or turn.output_tokens > 2048
                or type(turn.usage_complete) is not bool
            ):
                self.usage_complete = False
                raise _Halt("MALFORMED_MODEL_USAGE")
            self.usage_complete = self.usage_complete and turn.usage_complete
            self.tokens += turn.input_tokens + turn.output_tokens if turn.usage_complete else reserved_tokens
            self.input_tokens += turn.input_tokens
            self.output_tokens += turn.output_tokens
            if (
                self.tokens > self.agent.limits.max_total_tokens
                or turn.output_tokens > self.agent.limits.max_output_tokens
            ):
                raise _Halt("MODEL_TOKEN_BUDGET")
            self.prevalidate(turn.calls)
            if turn.continuation is not None:
                self.messages.append({"role": "model", "continuation": turn.continuation})
            for call in turn.calls:
                result = await self.execute(call)
                self.messages.append(
                    {"role": "tool", "name": call.name, "arguments": call.arguments, "data": result}
                )
                if self.selected is not None:
                    return
        raise _Halt("MODEL_REQUEST_BUDGET")

    def prevalidate(self, calls):
        """Reject an entire malformed batch before any external side effect."""
        validators = {
            "inspect_seed": _Args,
            "fetch_ranked": _Fetch,
            "evaluate_pool": _Snapshot,
            "finish_pool": _Snapshot,
            "stop": _Stop,
        }
        batch = set()
        for call in calls:
            if not isinstance(call, ToolCall) or call.name not in validators:
                raise _Halt("UNSUPPORTED_TOOL")
            try:
                validators[call.name].model_validate(call.arguments)
                signature = json.dumps([call.name, call.arguments], sort_keys=True, allow_nan=False)
                if len(signature) > 1024:
                    raise ValueError("argument size")
            except (ValidationError, TypeError, ValueError):
                raise _Halt("MALFORMED_TOOL_ARGUMENTS") from None
            if signature in self.signatures or signature in batch:
                raise _Halt("REPEATED_TOOL_CALL")
            batch.add(signature)

    async def execute(self, call):
        self.steps += 1
        if self.steps > self.agent.limits.max_tool_steps:
            raise _Halt("TOOL_STEP_BUDGET")
        if not isinstance(call, ToolCall) or call.name not in {
            "inspect_seed",
            "fetch_ranked",
            "evaluate_pool",
            "finish_pool",
            "stop",
        }:
            raise _Halt("UNSUPPORTED_TOOL")
        started = time.monotonic()
        target_domain = candidate_limit = None
        try:
            signature = json.dumps([call.name, call.arguments], sort_keys=True, allow_nan=False)
            if len(signature) > 1024:
                raise _Halt("MALFORMED_TOOL_ARGUMENTS")
            if signature in self.signatures:
                raise _Halt("REPEATED_TOOL_CALL")
            self.signatures.add(signature)
            if call.name == "inspect_seed":
                _Args.model_validate(call.arguments)
                result = {
                    "seed_id": str(self.seed.id),
                    "seed_domain": self.seed.domain,
                    "verified_target_domains": list(self.domains),
                }
            elif call.name == "fetch_ranked":
                args = _Fetch.model_validate(call.arguments)
                target_domain, candidate_limit = args.target_domain, args.limit
                result = await self.fetch(args.target_domain, args.limit)
            elif call.name in ("evaluate_pool", "finish_pool"):
                args = _Snapshot.model_validate(call.arguments)
                prepared = self.snapshots.get(args.snapshot_id)
                if prepared is None:
                    raise _Halt("UNKNOWN_SNAPSHOT")
                target_domain = prepared.feedback.target_domain
                if call.name == "finish_pool":
                    if self.remaining() <= 0:
                        raise _Halt("CURATION_DEADLINE")
                    if prepared.feedback.status != "ready" or not prepared.pool or not prepared.pool.path:
                        # Validator veto is feedback, never a model-overridable exception.
                        self.fact(call.name, "rejected", started, target_domain=target_domain)
                        return {"accepted": False, "feedback": prepared.feedback.model_dump(mode="json")}
                    self.selected = prepared
                result = {"accepted": True, "feedback": prepared.feedback.model_dump(mode="json")}
            else:
                args = _Stop.model_validate(call.arguments)
                raise _Halt(args.reason.upper())
        except (ValidationError, TypeError, ValueError):
            self.fact(
                call.name, "rejected", started, target_domain=target_domain, candidate_limit=candidate_limit
            )
            raise _Halt("MALFORMED_TOOL_ARGUMENTS") from None
        except _Halt:
            self.fact(
                call.name, "rejected", started, target_domain=target_domain, candidate_limit=candidate_limit
            )
            raise
        self.fact(call.name, "ok", started, target_domain=target_domain, candidate_limit=candidate_limit)
        return result

    async def fetch(self, domain, limit):
        if domain not in self.domains:
            raise _Halt("UNVERIFIED_TARGET_DOMAIN")
        if self.strategies:
            old_domain, old_limit = self.strategies[-1]
            if self.current.feedback.status == "ready":
                raise _Halt("UNNECESSARY_CORRECTION")
            if self.corrections >= self.agent.limits.max_corrections:
                raise _Halt("CORRECTION_BUDGET")
            if domain == old_domain and limit <= old_limit:
                raise _Halt("INEFFECTIVE_CORRECTION")
            supported_corrections = self.current.feedback.corrections
            if (
                domain == old_domain and "request_more_candidates_within_limit" not in supported_corrections
            ) or (
                domain != old_domain and "try_another_supported_target_or_seed" not in supported_corrections
            ):
                raise _Halt("INEFFECTIVE_CORRECTION")
            self.corrections += 1
        self.strategies.append((domain, limit))
        request = RankedCandidatesRequest(self.seed.id, self.seed.domain, domain, limit)
        result = await self.agent.provider.ranked_candidates(request)
        if result.error and result.error.code == "QLOO_AUTHENTICATION_FAILED":
            raise _Halt("QLOO_AUTHENTICATION_FAILED")
        self.received += len(result.candidates)
        observed = result.evidence.observed_at if result.evidence else self.now
        prepared = prepare_qloo_pool(
            result,
            request,
            rng_seed=self.rng_seed,
            now=self.now_override or datetime.now(UTC),
            evidence_expires_at=observed + timedelta(hours=24),
            confirmed_seed=self.seed,
            policy=self.agent.policy,
        )
        if self.remaining() <= 0:
            raise _Halt("CURATION_DEADLINE")
        self.rejected += prepared.feedback.candidates_rejected
        key = str(uuid4())
        self.snapshots[key] = self.current = prepared
        return {
            "snapshot_id": key,
            "feedback": prepared.feedback.model_dump(mode="json"),
            "remaining_qloo_http_requests": max(0, self.agent.limits.max_qloo_requests - self.budget.used),
            "corrections_remaining": self.agent.limits.max_corrections - self.corrections,
        }

    async def fallback(self):
        self.mode = CuratorMode.DETERMINISTIC_QLOO
        started = time.monotonic()
        # Preserve prior validator evidence and spent budgets; never reset after a failed model.
        if self.current and self.current.feedback.status == "ready":
            self.selected = self.current
        else:
            available = [domain for domain in self.domains if (domain, 20) not in self.strategies]
            if not available:
                raise _Halt("INSUFFICIENT_COVERAGE")
            await self.fetch(available[0], 20)
            if self.current.feedback.status == "ready":
                self.selected = self.current
            else:
                self.failure = "INSUFFICIENT_COVERAGE"
        self.fact("deterministic_fallback", "ok" if self.selected else "rejected", started)

    def outcome(self):
        if self.remaining() <= 0:
            self.failure = "CURATION_DEADLINE"
            self.selected = None
        prepared = self.selected or self.current
        succeeded = self.selected is not None
        status = (
            GenerationStatus.SUCCEEDED
            if succeeded
            else (
                GenerationStatus.TIMED_OUT if self.failure == "CURATION_DEADLINE" else GenerationStatus.FAILED
            )
        )
        receipt = CurationReceipt(
            game_id=self.game_id,
            curator_mode=self.mode,
            seed_entity_id=self.seed.id,
            seed_type=self.seed.domain,
            target_domains_considered=self.domains,
            target_domains_selected=tuple(dict.fromkeys(domain for domain, _ in self.strategies)),
            qloo_request_count=getattr(self.budget, "dispatched", self.budget.used) if self.budget else 0,
            qloo_reserved_count=self.budget.used if self.budget else 0,
            tool_request_count=self.steps,
            model_request_count=self.models,
            candidate_count_received=self.received,
            candidate_count_rejected=self.rejected,
            rejection_counts={},
            valid_pair_count=prepared.feedback.pool_pair_count if prepared else 0,
            bounded_correction_count=self.corrections,
            five_round_path_verified=bool(succeeded and prepared.feedback.five_round_path_verified),
            provider_version="qloo-v1",
            harness_version="0.1.26",
            model_version=self.agent.model.model_version if self.agent.model and self.models else None,
            validator_version=self.agent.policy.version,
            elapsed_ms=int((time.monotonic() - self.started) * 1000),
            model_input_tokens=self.input_tokens,
            model_output_tokens=self.output_tokens,
            model_usage_complete=self.usage_complete,
            action_trace=tuple(
                CurationAction(
                    tool=fact.action,
                    status=fact.status,
                    elapsed_ms=fact.elapsed_ms,
                    target_domain=fact.target_domain,
                    candidate_limit=fact.candidate_limit,
                )
                for fact in self.trace
            ),
            policy_fingerprint=self.agent.policy.fingerprint,
            policy_configuration=asdict(self.agent.policy),
            final_pool_status=prepared.feedback.status if prepared else None,
            final_feedback=prepared.feedback if prepared else None,
            evaluation_feedback=tuple(value.feedback for value in self.snapshots.values()),
            final_target_domain=prepared.feedback.target_domain if succeeded else None,
            status=status,
            created_at=self.now,
        )
        return CuratorOutcome(prepared, receipt, tuple(self.trace), self.failure)
