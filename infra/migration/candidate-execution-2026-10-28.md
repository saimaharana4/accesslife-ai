# Restricted candidate execution — 28 October 2026

**Acceptance is in progress, not a public release.** The first external run
reached a genuine agent-curated Qloo game and restored an accepted answer/Next
into round two, but did not finish the full test. Render review found missing
packaged artwork and an inaccurate local-preview label. Source fixes are under
CI; no public promotion is authorized from these partial results.

**Latest verified update:** the corrected candidate completed genuine
artist-to-movie generation, five answer/reveal transitions, save, invitation,
original social image and exact friend replay. The combined harness stopped on
one unavailable response-body observation. A repaired observer audits accepted
bodies before deliberately losing them; seven negative/positive contracts and
a strict provider-free live rerun passed, including both accepted-response
losses, two isolated five-round replays, save/reload and zero private fields or
unknown bodies. No extra provider call was used for those reruns. The remaining
current change is a bounded cold-forwarding deadline correction awaiting its
own CI/image refresh; no public promotion has occurred.

## Verified cloud changes

Project `project-bb13ecd8-9d67-408d-9a7`, `asia-south1`; unchanged remote-state
bucket/prefix and retained dedicated `accesslife-db` instance.

- Full-root migration plan: three creates; no updates, replacements or deletion.
  Saved-plan SHA256 `0cc934695658ba4a871765a8876627494045bd10dd7dd66b6078e75069b56cf2`.
- Full-root service plan: six creates; every other resource no-op.
  Saved-plan SHA256 `3656fc422b65638abe34d4a1eea257b1c922a8e7e856e012cf2c0eface5db46d`.
- Terraform source SHA256 for both plans:
  `0602ca90d76b03f0ecacbe6358a6ec0e87ed6350561df9e82115c92d785fc3d3`.
  Lead reviewed actual saved plans independently of the delegated resource-source
  author; machine scope/hash checks also passed. Saved binaries and journals are
  ignored private artifacts, not source files. Both exact plans applied.
- Only `tasteduel-migrate` executed, execution `tasteduel-migrate-bx9jm`, one task
  succeeded. Schema `td0010`; 22 application tables have forced RLS and migration
  ownership. Actual runtime insertion, cross-session read hiding and update
  denial passed in a rolled-back transaction. No application test rows committed.
- First revisions: `tasteduel-api-00001-2kv`, `tasteduel-web-00001-q2q`.
  **100% actual allocation, IAM restricted**, not zero traffic. No public IAM
  grant; API invocation belongs to web, web to the reviewed tester. Both rejected
  unauthenticated access with 403. Exact-origin web forwarding reached private
  API/database readiness with generation available; readiness alone is not play.

Canonical candidate origin:
`https://tasteduel-web-902056825143.asia-south1.run.app`.
It requires IAM authentication and is not a public demo. API token audience is
its actual service URI, separate from a possible revision-tag destination.
Secure host-only cookies and this exact mutation origin are configured.

## Immutable first candidate provenance

Application source `7acc6ed19d7c5678805c6e70d98327622d9a59c0` passed
[full CI](https://github.com/saimaharana4/taste-duel/actions/runs/40628638162).
Release-tool fixes on `90874f9` separately passed
[CI](https://github.com/saimaharana4/taste-duel/actions/runs/40630274772).
Local builds archived committed source only, used locked dependencies and baked
the pinned harness/Node runtime; no runtime package download or Cloud Build.

Registry prefix:
`asia-south1-docker.pkg.dev/project-bb13ecd8-9d67-408d-9a7/accesslife/`.

| Image | Verified immutable index digest |
|---|---|
| `tasteduel-api` | `sha256:96712f4266aa4cba8c21cf08b9d490d5bd794fe2cb7cd84c62c45c916fef6e5d` |
| `tasteduel-web` | `sha256:9415ed4e00661bf4ebffc0321a576a7cbe7a01caff740f79ee9912dc44a35c9a` |

Pinned Secret Manager references remain version **1** for
`tasteduel-runtime-database-url`, `tasteduel-migrate-database-url` and retained
`accesslife-qloo-api-key`. Web receives no secret access. Vertex uses API identity
IAM and `gemini-3.1-flash-lite/global`, SDK 2.33.0. The genuine first game proves
model access for this identity; it does not prove the full release journey.
Actual Qloo transport is the documented `http_ranked`/typed-search adapter; the
official harness remains packaged. Do not relabel HTTP calls as MCP workflows.

## Budget, rights and remaining gates

[Refreshed cumulative cost](candidate-cost-review-2026-10-28.md): **US$84.03 of
US$90**, US$5.97 headroom, through 7 November 10:15 IST, seven backups preserved.
First-attempt counts need reconciliation; the unchanged shared persisted caps
remain **12 Qloo upstream requests and six Vertex requests** for this stage.
Do not reset counters to retry. Authentication/startup/health do not establish
inference success or permission to exceed the live budget.

Only original title-card artwork and local licensed fonts are approved; no
optional external artwork is required. See [capabilities/rights](../../ai/qloo-capability-matrix.md)
and [asset manifest](../../third_party/taste-duel-assets.md). No raw Qloo response
is committed. Local screenshots and minimal private operator references remain
ignored, with the documented short evidence-retention policy.

Still pending: corrected immutable images and reviewed digest-only update,
complete external five-round run/exact friend replay/discovery/expiry/error
checks, reviewed desktop/mobile renders/full axe, secrecy audit and measured
warm/cold timing. Local clean-schema scoped in-memory logical restore passed;
cloud disposable-target rehearsal has not run. It will not establish a managed
Cloud SQL backup restore or a full durable export. Physical expiry cleanup and
manual human screen-reader/zoom/playtesting remain explicit release work.

No old job, worker, queue, ingestion, additional SQL instance, unrelated resource
or public traffic was introduced. Never restore over either live database.
Public promotion requires a separate passing release review.

## Corrected candidate and measured evidence

Source `091e7ea73ce18c27142ec5c11068036175e4721d` passed
[full CI](https://github.com/saimaharana4/taste-duel/actions/runs/40631606303).
Its API digest is `sha256:365b2dd92fd84100814a4ca2911e215bc53e6f522cbce67029caf1a6fe72994a`;
web digest `sha256:cdb88e6003999de5b5eb19f5ffbbf555b62dd5575d63776743c80a303d780691`.
A reviewed three-update image/source-label plan applied without other changes:
`4055dcf8fd439eb9e2e384998d21c70451cc5423aedac683df97f43dbd321420`.
Original artwork now loads; the misleading local-preview banner was removed.

The explicit two-call verification allowance changed only the API model limit
six to eight, saved-plan hash
`2b088614a5f237f2af059a4483beb000c789c532f7d2fcc8f80cc8ee10bf4ef8`.
It preserved `used=6`, window and expiry while increasing only the matching
private model-counter limit to eight. Current revisions before the cold fix:
`tasteduel-api-00003-n4n`, `tasteduel-web-00002-ctd`. Current finite stage totals:
**eight actual Qloo HTTP requests and eight Vertex calls**; ceilings twelve/eight.
Genuine generation is now closed for this review. Candidate anonymous activity
stays excluded from production analytics denominators.

The final genuine receipt records 20 candidates, zero primary exclusions,
15 valid pairs, a complete no-repeat path, zero forced corrections, one real
ranking request and two real Vertex decisions. The model selected a 20-candidate
movie strategy, then finished only after deterministic ready feedback.
Curator elapsed9.376s, 1,267 input/75 output tokens; no psychological narrative
or hidden reasoning is exported. These are one execution's facts, not human
impact, calibrated difficulty or a success-rate estimate.

Cloud Run answer request latency: **37 samples, median225.08ms, p95 277.15ms**,
private automated play across candidate revisions in `asia-south1`. This includes
service/DB/proxy overhead; it is not isolated CPU time, field INP or user p75.
Deployment/autoscaling system start-to-startup-probe intervals were approximately
3.1–3.2s for web and 15.1–18.1s for API; latest API observation15.821s.
These are container startup intervals, not a measured end-user cold navigation.
They exposed the former 12s proxy deadline as inadequate. Forwarding is being
changed to finite25s ordinary /35s search /45s generation deadlines while the
API generation deadline stays20s. Fake-clock checks prove an18s API start can
finish and a hung call still returns a sanitized retryable timeout.

Cloud logical recovery **PASS**: two owner-scoped sessions, 40 table/session
counts and 36,678 private in-memory bytes; exact row digest/counts matched,
two completed scores and one frozen challenge were verified, and a fresh guest
played five restored rounds through the real API without providers. Only the
new marked disposable database was removed. No live DB was restored over, no
payload backup file/new instance was created. **Managed Cloud SQL backup restore
and durable full-database export remain unproven.**

Actual owned-challenge expiry returned410/`CHALLENGE_EXPIRED`, no choices, and
an intentional page; historical answers were unchanged. A controlled original-
artwork404 retained titles and 320px layout. Both passed complete axe scans.
Desktop/mobile/reflow and original OG captures were inspected; no external art
was introduced. Native screen-reader/zoom user testing and consenting human
playtests remain pending, not inferred from automated scans.

Final refreshed cost **PASS: US$83.77 / US$90**, headroomUS$6.23, through
7 November10:15IST. The last pre-cold-fix full-root refreshed plan had
**zero changes**, saved-plan hash
`5ad48603f5fc5c011e82a61303614bf1fa1fa8ced6d23dd902b83cd0e05ce6ef`.
Cold-fix images, its reviewed refresh and final CI/state checks remain to record.
