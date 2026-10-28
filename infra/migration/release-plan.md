# Taste Duel release review plan

**Current execution ? 28 October 2026:** IAM-restricted Taste Duel candidate resources are deployed; full external acceptance is still incomplete. [Actual changes, reviewed plans and open gates](candidate-execution-2026-10-28.md). The earlier preparation/inventory statements below are historical, not current deployment status.

27 October 2026. **Preparation only; no images published, services provisioned,
migrations executed, traffic changed or apply-ready plan produced.** This follows
the separately reviewed [foundation plan](foundation-plan.md), never a targeted
subset of the legacy deployment.

## Lean topology and region

Public `tasteduel-web` (Next.js) → same-origin allowlisted `/api/v1` forwarding →
IAM-private `tasteduel-api` (FastAPI and one managed official MCP subprocess) →
existing `accesslife-db` instance/new `tasteduel` logical database. One
`tasteduel-migrate` job uses the separate migration identity. PostgreSQL 16 is
ordinary relational storage; no new PostGIS/vector requirement, worker, queue,
embedding/ingestion service, VPC connector or always-on second SQL instance.

Runtime and SQL remain in `asia-south1`. Model configuration stays the previously
tested `gemini-3.1-flash-lite` at **global**, SDK 2.33.0. That historical model
smoke does not prove access for the not-yet-created API identity, model capacity
on release day, or India-only data processing. Verify the selected model/identity
after foundation; do not invent a Mumbai model endpoint. Qloo remains external.
Regional availability/cost evidence is in [cost/IAM review](cost-and-iam.md).

## Real release inputs and current blockers

Required inputs: tested source SHA/current CI, actual immutable registry digests,
published controlled bootstrap digest, SQL connection name/new credentials by
Secret Manager version reference, scoped identities, verified API audience and
actual canonical web origin. There are no placeholder image defaults.

The current local application deliberately rejects cloud database connections:
`config.validate_local_url` and `tasteduel_migrations/env.py` require the isolated
local/Compose database and role names. The cloud socket/new `tasteduel` database
mode, explicit privilege bootstrap and expiry-cleanup execution must be designed,
tested and reviewed before this job can run. This review does not claim that
the current local migration command is cloud-ready.

Use the real web configuration keys `TASTEDUEL_API_URL`,
`TASTEDUEL_WEB_ORIGINS`, `TASTEDUEL_API_IAM`, `TASTEDUEL_CANONICAL_ORIGIN`
and keep the API URL at the canonical API service origin, which the current
forwarder also uses as its token audience. A separate candidate-URL/audience
override is not currently implemented; test such a change before using API tags.
Check the actual forwarding/identity-token contracts before release;
legacy `API_INTERNAL_URL` is not a substitute. API gets exact allowed mutation
origins, secure host-only cookies, reviewed Qloo transport/typed-search settings
and pinned secret versions. Web never receives provider/database credentials.

## Controlled future action set

1. Recheck cumulative cost and incur only the reviewed build/registry allowance.
   Build immutable images from the tested lean containers; do not publish or
   deploy the old AccessLife image/entrypoint. Keep its digests for rollback.
2. Create new services through an explicitly reviewed administrative bootstrap.
   A first Cloud Run revision normally gets initial traffic; do not call it
   zero-traffic by assumption. Use an approved maintenance response with controlled
   access or an actually IAM-restricted initial service, then deploy product
   candidate revisions with no production allocation. A public revision tag is
   still reachable and is not an access-control boundary.
3. Produce a separate full saved release plan using those real digests and
   foundation state. Bind deployment update/invoke rights to the actual new
   services/job. Preserve old services, DB/user, registry, state and current
   production traffic. New service addresses are separate from legacy ones.
4. Execute only the new Taste Duel migration job after cloud guards/DB privileges
   pass; no ingestion/reconcile/extension or corpus steps. Verify runtime cannot
   perform schema DDL or read AccessLife. Do not log connection payloads.
5. Configure min instances zero, max web/API initially two each, bounded
   concurrency and awaited generation deadlines. Keep SQL connection pools small
   and respect the shared six-Qloo/four-model generation ceilings and daily budgets.
   Legacy provider admission does not automatically coordinate with Taste Duel;
   resolve key-wide overlap before public generation. No post-response worker.
6. Validate external genuine generation, five rounds, explicit save, identical
   two-session challenge, recovery, expired states, keyboard/mobile/axe and
   answer/secret isolation. Identity-token audience remains the canonical API
   service even if requests use a candidate-tag URL. Remove temporary candidate
   mutation origins after the later production promotion.
7. Rehearse only a priced disposable restore. Logical export/restore does not
   prove managed Cloud SQL backup restore. Never overwrite either source DB.
   Daily event cleanup and evidence/challenge expiry reconciliation need an
   explicit verified operational path; do not add an undeclared worker service.

## Rollback, cutover and retirement

This stage must not split users randomly between AccessLife and Taste Duel.
Cutover to the new service URL is a later explicit release action after all
candidate gates pass. Future percentages can split compatible Taste Duel
revisions, with web/API/schema compatibility controlled together.

Retain old data, compatible image manifests, configuration and required secret
readers at least seven days after verified cutover and through judging/follow-up.
This does not require old schedulers/workers to execute for seven days: drain
accepted work and pause/retire only under an authorized, priced decision.
Later cutover extends retention and requires repricing. Preserve compatible Taste
Duel rollback revisions without changing accepted answers or frozen challenges.
Rehearsal and managed restore remain pending; recorded ready revisions are only
rollback targets. Data/key deletion and project teardown are separate actions.
