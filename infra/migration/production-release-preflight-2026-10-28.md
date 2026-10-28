# Taste Duel production release preflight

Historical preflight reviewed 28 October 2026. **Its candidate blockers were subsequently resolved by the explicitly approved bounded attempt.** See the [current execution record](production-release-execution-2026-10-28.md). The baseline and proposal below describe the earlier review; they are not current usage or a production approval.
This is a concrete review plan, not an executable saved plan or permission to
promote. Three independent reviews covered controlled release, external browser
acceptance, and IAM/observability. No infrastructure, provider budget, public
access, repository About, or traffic was changed during this preflight.

## Exact baseline

- Repository HEAD: `2ddd6eed04f8acadfb942318c03c07c0acba6199`; application image
  source: `83ede4499ef53ebfcafc9895835b047fbed4b5c6`. Their recorded CI runs
  `40659317166` and `40655258903` succeeded.
- Project `project-bb13ecd8-9d67-408d-9a7`, region `asia-south1`, remote-state
  serial 27 in the existing bucket/prefix. Last refreshed full-root plan had
  zero changes; it is historical evidence, not a new public-release plan.
- Canonical web: `https://tasteduel-web-902056825143.asia-south1.run.app`.
  API: `https://tasteduel-api-dfthmgvvaa-el.a.run.app`.
  One unauthenticated GET to each returned **403** in this review.
- Web `tasteduel-web-00003-9xv`, image
  `sha256:0e80d82503a71404e05ed5e0ff4762eac5eec916e0f2783ba2fe7dd0e0e1cddd`.
- API `tasteduel-api-00004-lmb`, image
  `sha256:fe3eed0e056ad9a72c3b63919c9effb26c0d7030945be76b2b9f6f6834e1102f`.
- Schema `td0010`, existing dedicated SQL instance/new `tasteduel` logical DB,
  pinned Secret Manager versions 1. Old database/user remain retained.
- Both services have actual 100% allocation under IAM restrictions. This is
  neither public availability nor zero-percent initial traffic.

Source and private evidence are detailed in the
[candidate execution record](candidate-execution-2026-10-28.md).
User edits to `ai/prompts.md` and deletion of `ai/prompt8-curator.md` remain
untouched. No credential-history file or secret payload was read for this review.

## Candidate closure required before production implementation

1. **Fresh final-image journey:** the completed source game expired. The record
   explicitly says `NOT_RERUN_ON_FINAL_IMAGE`; do not revive evidence. Earlier
   genuine play/replay remains useful evidence for unchanged backend/scoring,
   but is not a fresh full acceptance of the final compatible configuration.
2. **Finite live allowance:** eight Vertex calls have been consumed and that
   verification allowance is closed. The existing eight Qloo HTTP calls leave
   four under its absolute twelve-call ceiling. Do not reset counters/windows.
3. **Cold request timing:** measured container startup and warm requests do not
   establish end-to-end cold latency. The last 200/484ms probe had no autoscaling
   event. Use a provider-free health/session path and correlate actual startup
   events; report an unproven result honestly if the instance stays warm.
4. **Cost:** US$90 is the approved cumulative ceiling. US$83.77 was the forecast
   using billing observed at 10:51 IST, not newly approved public capacity.
   Refresh accrued gross bounds and price quotas, monitoring, cleanup and the
   rollback window through at least 7 November 10:15 IST before changes.

Smallest proposed candidate-only allowance, **not applied or approved here**:
one generation attempt, expected two Qloo/two Vertex requests; hard ceilings
of **four additional Qloo and two additional Vertex**. Absolute stage ceilings
would become **twelve Qloo/ten Vertex**. Any eligible transport retry/internal
lookup counts inside those ceilings; no additional game attempt or automatic
allowance extension. A reviewed API configuration change and the exact existing
model admission row must preserve used=8, window and expiry while raising only
its limit to ten. A configuration-only change cannot silently widen the row.
Stop on failure. The existing monetary reserve must be rechecked; this proposal
does not increase the US$90 ceiling or approve a public quota.

Run the corrected strict cloud journey on the exact accepted configuration:
typed search -> genuine curator/Qloo -> five answers/reveals -> explicit save ->
challenge -> isolated identical five. Include lost accepted answer/Next responses,
keyboard, reduced motion, desktop/390px/320px, full axe and HTML/JSON/OG secrecy.
Answers, Next and fixed replay must use zero external-provider calls.

Managed Cloud SQL backup restore is a separate unproven operation; the priced
scoped logical restore passed. Human playtests/native screen-reader/zoom remain
explicit limitations, not results inferred from axe. No serious accessibility
defect has been established by this preflight.

## Release action plan once those prerequisites pass

| Phase | Exact scope and gate |
|---|---|
| Prepare | Review public quotas/cost and compatible API/schema/web manifest. Build and run CI before immutable publication. Preserve source SHA, digests, configuration and secret versions. No mutable image tags. |
| Operational readiness | Implement/test narrowly scoped physical expiry cleanup and a priced execution mechanism. The local-only `events-purge` command is not a cloud retention implementation. Do not improvise broad cross-session deletion or silently add a worker. |
| Privacy/monitoring | Replace the old AccessLife uptime target with Taste Duel readiness; add sanitized generation outcome/error/admission signals. Exclude Taste Duel search request logs that contain query text without deleting unrelated logs. Readiness must distinguish configured generation from remaining admission capacity. |
| Migration | Run only the Taste Duel migration job if a reviewed backward-compatible schema change exists. Never rerun legacy ingestion/reconcile or restore over a live DB. Preserve accepted games/challenges. |
| Pin baseline | Full-root reviewed plan explicitly pins accepted API/web revisions. Current `LATEST=100%` policy is insufficient for a controlled no-traffic candidate. Preserve the canonical API token audience and exact canonical mutation origin. |
| Deploy candidate | Deploy published compatible digests to the existing services with no production allocation. Explicitly control tagged-web access: a public tag is reachable even at zero percent. Add only exact temporary candidate origins and remove them after testing. |
| Restricted smoke | Run genuine accepted-configuration play and provider-free exact replay within a separately recorded allowance; confirm private API, cookies, secrecy and persistent state. No readiness-only substitute. |
| Rollback rehearsal | Test the compatible revision/configuration rollback below while retaining stored data; return to the accepted pair and verify again. |
| Public cutover | Apply only the independently reviewed saved promotion plan. Public invocation belongs to `tasteduel-web` only; API remains private. Explicit named revision allocation must select compatible web/API configurations. Never split traffic between AccessLife and Taste Duel. |
| Publish identity | Set actual canonical origin consistently in metadata, exact origins, share/OG links, README, GitHub About and monitoring. No purchased-domain claim. New host-scoped guest cookies create a fresh session; no parent `.run.app` cookie. |
| Independent public check | Unauthenticated landing/search -> genuine five -> actual score/save -> isolated exact challenge; mobile, keyboard/reduced motion, private API rejection, secrecy, readiness/meaningful alerts and cost. No promotion pass on a partial test. |

Existing release tooling supports only migration/services/refresh and one narrow
verification allowance change. `cloud-release.yml` is a retired no-op. New
promotion/rollback scopes, named-revision routing, workflow stages and saved-plan
reviews must be implemented/tested after candidate acceptance. Public quota
values, cleanup execution mechanism, monitoring pricing and new revision IDs
are **unresolved inputs**, not invented executable references.

## Rollback compatibility and authority

- Current accepted-code baseline is API4/web3 above, schema `td0010`. Old API
  `tasteduel-api-00003-n4n` uses digest
  `sha256:365b2dd92fd84100814a4ca2911e215bc53e6f522cbce67029caf1a6fe72994a`
  and the same backend/schema. A restricted provider-free API4 -> API3 -> API4
  rehearsal with web3 retained is a useful compatibility test, **not yet run**.
- Retain web3's cold-start correction. Do not use web2 as an equivalent rollback:
  it has the known 12-second forwarding deadline.
- API3/API4's eight-call policy is not an adequate public rollback configuration
  after a larger allowance is approved. Prepare a compatible rollback revision
  with the same reviewed public limits/secret references; an old lower policy can
  reduce admission again. Preserve usage, fencing, accepted answers and snapshots.
- Before/after rehearsal, compare owner-scoped stored game/challenge state and
  run provider-free reads/replay where unexpired evidence exists. Never extend
  expired evidence to make the rehearsal pass. Rehearse a fresh challenge first
  while its genuine evidence remains valid.
- Deployment rights stay resource-scoped. `roles/run.developer` does not grant
  public service IAM administration. Use separately reviewed web-scoped IAM
  authority; do not give the deploy identity project-wide Run administration.
  WIF must retain numeric repository/owner and branch/environment restrictions.
- AccessLife recovery remains a separate historical path with retained data,
  images, state and readers; it is not a random alternative production target.

**Decision:** no production implementation, public IAM grant, traffic promotion,
new provider call, counter reset, domain change or About update is authorized by
this failed preflight. First resolve the bounded candidate allowance/cost and
acceptance gate; then execute the reviewed production plan.
