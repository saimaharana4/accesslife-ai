# Controlled Taste Duel candidate release

Production promotion is currently blocked by the
[dated candidate-gate and release/rollback preflight](../migration/production-release-preflight-2026-10-28.md).
This document's candidate tooling does not implement public promotion.

This configuration prepares two explicit full-root releases after the applied
foundation. It does not enable public access. Each actual plan needs independent
review, refreshed cumulative-cost approval and a separately authorized apply.
Both feature switches default false for unconfigured clones; preserve true
applied switches in every later reviewed plan to avoid proposing removal.

## Immutable source and images

`scripts/tasteduel_release_images.py` verifies the exact successful main-push CI
run, archives the committed SHA, and builds only that archive with the existing
locked dependencies/pinned base images. Uncommitted production inputs block it;
unrelated user notes never enter the archive. Both final images contain OCI
source/revision labels. Runtime dependencies and the pinned official harness
are baked in; no package installation occurs at startup.

After build/push budget approval, use the actual reviewed values:

```powershell
uv run --project runtime/python --frozen python scripts/tasteduel_release_images.py --review .data/tasteduel-cloud-review/approved-cost.json --source-sha ACTUAL_CI_SHA --ci-run-id ACTUAL_SUCCESSFUL_RUN --execute
```

The private output `images.json` records real registry digests, source/archive
hash and CI evidence. The script configures only the local gcloud Docker helper;
it never prints tokens, deploys services or runs Terraform. Image publishing is
an explicit registry mutation, not a static check. Without `--execute` it remains
preparation only. Do not substitute old AccessLife images, local tags or invented
digests to make a Terraform plan succeed.

## A: migration job only

Enable `tasteduel_release_migration_enabled`, keeping service enablement false.
Use both published image digests and the same source SHA as reviewed inputs.
Generate the full-root saved plan with `scripts/tasteduel_release_plan.py`:

```powershell
uv run --project runtime/python --frozen python scripts/tasteduel_release_plan.py --review .data/tasteduel-cloud-review/approved-cost.json --images ACTUAL_IMAGES_JSON --phase migration --tester user:REVIEWED_TESTER --project-number ACTUAL_PROJECT_NUMBER
```

The plan runner reads established version-1 credential references into memory,
retaining identical existing SQL/secret inputs. It captures provider JSON in
memory and exports only allowlisted action metadata/hashes. The binary plan is
sensitive and ignored. No apply command, targeting or job execution is included.
Expected changes are the release gate, new `tasteduel-migrate` job and its
resource-scoped deploy binding. All foundation/legacy data resources must remain
no-op. Changes outside this set block the automatic review.

After independent plan review and authorized application, execute only the new
migration job. It mounts managed `/cloudsql`, uses the separate migration identity
and exact Secret Manager URL reference, with one task, no retry and a five-minute
timeout. No ingestion, reconcile, extension installation or synthetic venue/data
seed is required. Verify schema revision, runtime DML/RLS isolation and preserved
old database access boundaries before service creation.

## B: IAM-restricted services

Only after migration verification, keep A enabled and enable services. Produce a
second full-root saved plan with the same images and `--phase services`. Initial
Cloud Run revisions receive **100% real allocation**, not zero percent. Access
is deliberately IAM restricted: API invocation belongs to web's identity; web
invocation belongs only to one reviewed test-user grant (plus any pre-existing
project/organization inherited permissions, which need independent review).
There is no `allUsers` or `allAuthenticatedUsers` grant and no public promotion.

Both services scale to zero with one-instance maxima. API uses eight-request
concurrency and a two-connection/no-overflow pool; web concurrency is twenty.
CPU is request-billed with startup boost disabled. Initial test budgets are
twelve Qloo upstream requests/day, twelve/minute, eight Vertex requests/day and
500,000 total Vertex tokens/day. These are ceilings, not permission to make
unrecorded probes: a shared actual-attempt ledger must count harness-internal
lookups/retries and stop at the approved tiny live budget. The actual verified
transport is `http_ranked` with typed HTTP search; the official pinned harness
remains packaged. No claim of canonical MCP ordering is substituted for that
documented transport decision.

The initial six-model-call allowance was explicitly revised once by a reviewed
API-only plan; existing usage/window/expiry were preserved, not reset. See the
[dated cost review](../migration/candidate-cost-review-2026-10-28.md). Digest-only
candidate updates use `--phase refresh`; any policy/IAM/data change blocks that
mode. The one-time `verification-budget` scope permits only the reviewed6→8 API
setting and is not a general quota-increase command. Stop genuine generation
after the recorded eight-call ceiling; provider-free replay remains testable.

The web origin uses Google's documented deterministic service/project-number
format, avoiding a circular self-URI dependency. Verify its real service alias
and TLS response after creation before browsing. Web requests and ID-token
audience use the actual API `uri` independently. See
[Google's URL documentation](https://docs.cloud.google.com/run/docs/triggering/https-request).
Allowed mutation origins contain only the exact reviewed web origin. Database
and Qloo references pin numeric versions; web receives no secret references or
payloads. Secure host-scoped cookies remain enabled.

Controlled browser authentication must inject the operator identity token only
for that exact web host, using `X-Serverless-Authorization`. Never set global
browser headers that could send credentials to artwork/third-party origins.
Verify unauthenticated web/API rejection, web-to-private-API connectivity, real
five-round gameplay and identical challenge replay separately from readiness.

## Preservation and follow-up

Old databases/users, instance/backups, registry and backend remain at their
existing addresses. The release creates no worker, queue, scheduler, VPC
connector, additional SQL instance or cloud project. IAM update/deploy grants
are bound to the actual new services/job, not project-wide Run administration.

No static pass, image push, readiness response or IAM-restricted initial revision
is a passed external-gameplay, human-impact, restore or public-release gate.
Record actual images, schema, secret versions, timings and plan hashes after
execution. Reprice if cutover extends the seven-day rollback window. Public
promotion belongs to the next separately reviewed release stage.

## Recorded restricted execution

The final image-only refresh and zero-change plan are recorded in the
[dated execution evidence](../migration/candidate-execution-2026-10-28.md).
Application `83ede44` passed remote CI; state 27 preserves both databases and pinned
secret versions. The migration job was not rerun for a forwarding-only change.
Genuine generation is closed at eight actual Qloo/eight Vertex calls; earlier
frozen evidence has expired, so a fresh final-image replay was not fabricated.
Candidate IAM remains restricted. Public promotion/quota/physical-retention review
belongs to a separately authorized release action.

## Current controlled release

The approved candidate closure passed at ten actual Qloo HTTP/ten Vertex calls; that ledger is closed. See [current execution](../migration/production-release-execution-2026-10-28.md) and [US$88.15 forecast](../migration/production-cost-review-2026-10-28.md). The production source adds td0011 and requires a new compatible rollback pair; API83ede44 requires td0010 and must not be labelled a healthy rollback. Public release remains pending actual CI, exact saved plans, sealed-config and public-browser checks.
