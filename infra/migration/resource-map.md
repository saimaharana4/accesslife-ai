# Taste Duel resource migration review

**Current update, 27 October 14:09 UTC:** explicitly authorized legacy runtime retirement is complete; shared assets remain. Original read-only findings below are historical. See [execution and reconciliation](retirement-options.md). New foundation provisioning remains blocked.

Reviewed **27 October 2026**, project `project-bb13ecd8-9d67-408d-9a7`, region
`asia-south1`. This is a read-only migration design. No apply, deployment,
database mutation, repository rename or traffic change is authorized by this review.

The selected-metadata inventory was captured at **11:51 UTC / 17:21 IST** using
ADC and 31 read requests, with zero failed requests. The private artifact is
`.data/tasteduel-cloud-review/inventory.json`; regenerate with
`uv run --project runtime/python --frozen python scripts/tasteduel_cloud_inventory.py`. It contains no environment
values, task bodies, database rows, secret payloads or state contents. No Qloo or
Vertex inference was requested. Other workloads are outside this boundary.

## Historical runtime and rollback image targets

At the original 11:51 UTC snapshot, all three services routed **100% to their latest ready revision**. The
web was the public AccessLife product; API and worker access must continue
to be assessed through their IAM policies, not their ingress setting alone.

| Existing service | Current revision / rollback reference | Runtime | Configured image-index digest | Resolved revision manifest digest |
|---|---|---|---|---|
| `accesslife-web` | `accesslife-web-00005-smn` | 1 CPU / 1 GiB; revision max 2; concurrency 80; 300 s | `sha256:4fd3995f835d59ed0801d94ae8bdec2707953774f84880754442da2930b10346` | `sha256:18dfac5667e4b21dc3d5541bbcca2c19ce803382dfc3359714ea7dfd5097de49` |
| `accesslife-api` | `accesslife-api-00003-lcv` | 1 CPU / 1 GiB; revision max 2; concurrency 20; 120 s | `sha256:fe4be430367838a54b6f397351c3f9381c922a15ec65a8b9b597c381ae533474` | `sha256:590fb0672f7bb83eb00691b069bc0053cbd1ffedbd5dff567b11fd1bed2008f2` |
| `accesslife-worker` | `accesslife-worker-00003-72z` | 2 CPU / 4 GiB; revision max 1; concurrency 3; 120 s | same API index above | same API manifest above |

The registry base is
`asia-south1-docker.pkg.dev/project-bb13ecd8-9d67-408d-9a7/accesslife/`, with
`web@<digest>` and `api@<digest>`. An OCI index digest and its resolved platform
manifest are distinct identifiers; this difference alone is not configuration
drift. Both are recorded so a rollback does not depend on mutable tags. Earlier
revision metadata and digests are retained privately; their runtime compatibility
has not been newly tested in this review. These current rollback targets were
reported ready by Cloud Run, which is not a new end-to-end rollback rehearsal.

Current URLs remain:

- `https://accesslife-web-dfthmgvvaa-el.a.run.app`
- `https://accesslife-api-dfthmgvvaa-el.a.run.app`
- `https://accesslife-worker-dfthmgvvaa-el.a.run.app`

Future Taste Duel URLs must come from actual service outputs. No purchased domain
or predetermined `.run.app` hostname is assumed. AccessLife and Taste Duel are
different services, not traffic percentages of one revision history.

## Old → new/reused → retired mapping

| Dedicated existing resource / owner | Taste Duel disposition | Retirement and release boundary |
|---|---|---|
| `accesslife-web` / `google_cloud_run_v2_service.web` | New public `tasteduel-web`, scale to zero, bounded instance maximum; web-to-private-API forwarding only | Preserve old revision/digests until deliberate cutover and rollback-window close; no traffic changes in this review |
| `accesslife-api` / `google_cloud_run_v2_service.backend["api"]` | New IAM-private `tasteduel-api`, awaited bounded generation; same-origin browser boundary | Do not reuse old app entrypoints, database URL or old worker token |
| `accesslife-worker` / `google_cloud_run_v2_service.worker` | No Taste Duel worker service | Drain accepted old runs and dependencies before the later retirement stage; do not delete now |
| `accesslife-migrate`, `accesslife-ingest`, `accesslife-reconcile` / `google_cloud_run_v2_job.maintenance` | One new `tasteduel-migrate` job, separate migration identity, Taste Duel Alembic only | Never run AccessLife ingestion/reconcile as part of a Taste Duel release |
| Scheduler `accesslife-reconcile` / `google_cloud_scheduler_job.reconcile` | No new Taste Duel scheduler required for core gameplay; expiry maintenance needs an explicitly reviewed execution path | Existing job is **ENABLED every five minutes**, 932 executions observed; pausing requires later authorization and accepted-run checks |
| Queue `accesslife-planning` / `google_cloud_tasks_queue.planning` | No Taste Duel queue; awaited reservation/lease recovery already owns generation | Existing queue **RUNNING**, zero queued tasks in metadata observation; recheck before drain/retirement, do not purge now |
| SQL `accesslife-db` / `google_sql_database_instance.db` | **Reuse the same physical instance**; PostgreSQL 16, Mumbai, zonal Enterprise `db-custom-1-3840`, 20 GiB SSD / growth cap 40 GiB | Immutable-name exception. Keep deletion protection; no second always-on SQL instance, renaming or replacement |
| Logical database `accesslife` / `google_sql_database.app` | Keep unchanged; add new logical database `tasteduel` at a **new resource address** | Never change `google_sql_database.app.name` to create Taste Duel: that can replace/drop the old logical database |
| SQL user `accesslife` / `google_sql_user.app` | Retain unchanged; add separate `tasteduel_runtime` and `tasteduel_migrate` users/roles with fresh credentials where required | Never rename/reuse the old user's resource block or credentials; old user remains for bounded rollback |
| Existing SQL `postgres` logical DB/user | Administrative/system prerequisite, not app ownership | No deletion, privilege change or adoption into app-managed resources |
| Registry `accesslife` / `google_artifact_registry_repository.images` | Reuse with new `tasteduel-web` / `tasteduel-api` image packages and immutable digests | Immutable-name exception: new repository adds migration/retention work without product value. Preserve rollback manifests; no blanket cleanup |
| `accesslife-docs-<project>` / `google_storage_bucket.private["docs"]` | Legacy corpus only; Taste Duel has no ingestion/corpus requirement | Retain under current permissions until source/backup/rollback review; no new dataset copy or bulk migration |
| `accesslife-backups-<project>` / `google_storage_bucket.private["backups"]` | Reuse only if approved for private dated Taste Duel logical exports under a new prefix | Keep old exports separate, bounded and source-policy compatible. Do not erase during branding |
| `accesslife-tfstate-<project>/accesslife/state` | **Preserve bucket, prefix, versioning and state ownership** | Bootstrapped outside the module; no bucket move or empty-state recreation during identity changes |
| Secret `accesslife-qloo-api-key` version 1 ENABLED | Temporarily retain exact reference and pin released version; grant only new API reader if reviewed | Immutable-name exception. Same-key copy is not provider rotation; preserve old readers until overlap ends, never disable shared key early |
| Secret `accesslife-db-password` version 1 ENABLED | Legacy SQL credential only | Do not copy into Taste Duel; revoke only after old DB/runtime rollback ends |
| Secret `accesslife-database-url` version 1 ENABLED / `google_secret_manager_secret.database` | Legacy URL only; fresh Taste Duel runtime/migration secret references | Preserve legacy secret resource and injected versions until old readers retire |
| Secret `accesslife-worker-token` version 1 ENABLED | No Taste Duel dependency | Retire only after task/worker/job dependencies and queued headers are resolved |
| `accesslife-web/api/worker/task/ingest/deploy` service accounts | New narrowly scoped `tasteduel-web/api/migrate/deploy`; no worker/task/ingest identity needed | Keep legacy identities/grants for rollback, then revoke identified grants deliberately; never mass-remove project IAM |
| WIF pool `accesslife-github`, provider `github` | Retain physical pool name if useful; restrict trust to verified numeric repository/owner plus intended main/environment | Coordinate repository rename and trust in the foundation stage. Existing name-based trust is not proof renamed identity works |
| Repository `saimaharana4/accesslife-ai` | Future rename to `saimaharana4/taste-duel` only if available, preserving history/tags/licence | No rename here; old URLs may redirect, but WIF/release/environment permissions require explicit verification |
| Existing CI and legacy deploy workflow | CI remains synthetic; replace legacy deployment before executing a Taste Duel release | Do not let old ingestion commands or hardcoded expiry gates become an unreviewed release path |
| Uptime `AccessLife public web` | Add/update Taste Duel uptime/readiness only when real URL exists | Keep correct old monitoring during overlap; do not point alerts at nonexistent URLs |
| Billing alert `AccessLife hackathon USD80 alerts` | Aggregate both migration labels / reviewed shared budget coverage, plus manual unlabelled-cost ledger | Labels/alerts are not complete accounting or spend caps; do not double-count reused SQL or hide legacy costs |
| `app=accesslife, environment=hackathon` labels | New resources `app=tasteduel`; shared infrastructure gets explicit shared ownership/accounting | Report old/new label sets and unlabelled model/network/build costs through the full reviewed window |

`<project>` in the bucket rows means exactly `project-bb13ecd8-9d67-408d-9a7`.
No app data, keys or state is copied just to change a visible product name.

## Storage, retention and database boundary

The inventory shows only `accesslife` and `postgres` databases/users; the new
Taste Duel database/users do **not** yet exist. SQL backup metadata reports three
successful automated backups. Retention is seven backups; PITR is **disabled**.
Do not claim point-in-time recovery or a tested managed restore. New Taste Duel
schema uses ordinary PostgreSQL; existing PostGIS/vector installation is not a
requirement and is not removed from the old database.

Runtime receives only its own database DML privileges and required sequence
access; migration owns its schema and may run DDL. Cloud SQL client IAM is the
connection permission, not PostgreSQL table authorization. Verify CONNECT/schema
isolation against the deployed database in the foundation stage; merely creating
a Cloud SQL built-in user does not prove least-privilege PostgreSQL grants.

Retain AccessLife logical DB/user, compatible old images, required secret
versions and state for at least **seven days after a verified Taste Duel cutover**
and no earlier than **6 November 2026 10:15 IST**. This is a proposed minimum
review window, not permission to delete automatically. The cumulative cost review
must include that actual endpoint; if the future cutover extends it, reprice
before extending runtime/storage. At window close require recovery evidence,
reader/drain checks and an explicit retirement decision. Source-permission
expiry takes precedence over indefinite evidence retention; preserve operational
metadata separately from any provider data that must be purged. Existing backups
age out by their configured policy; session clear does not rewrite them.

Seven-day recovery retention means keeping logical data, images, compatible
configuration and only the access needed to recover. It does not require the old
scheduler/worker to keep executing for seven days: after a healthy cutover and
accepted-run drain, later authorized retirement can stop obsolete execution while
preserving rollback assets. The cost follow-up assumes a 31 October cutover and
covers the resulting 7 November endpoint; later cutover requires reforecast.

All three dedicated buckets enforce public-access prevention/uniform access and
versioning. The state bucket currently has no app billing label. Its observed
object is `accesslife/state/default.tfstate`, generation `1792824552399397`,
142,722 bytes, updated 24 October 06:49 UTC. This is object metadata only: no
state values were printed by the inventory. Bucket soft-delete retention is
seven days. Archived-object lifecycle deletion (7 days backups / 30 days docs)
does **not** expire live objects; account for retained live files explicitly.

## Ownership/drift and staged plans

Keep all legacy addresses stable in the currently owned remote state. Adding new
Taste Duel resources is not renaming the old resource blocks. If a later reviewed
refactor changes an address, use explicit `moved` blocks; if an already-existing
owned resource is missing from state, first verify its ID and use an explicit
import rather than creating a duplicate. Never adopt unrelated resources.

Read-only inventory is not a Terraform drift reconciliation. The refreshed plan
must separately compare source, remote ownership and observed metadata, retaining
the actual current legacy image indices/URL and scheduler status. Service-level
Cloud Run max-instance metadata is 5 while revision-level caps remain 2/2/1;
record both without assuming one replaces the other. Review defaults and computed
fields before classifying a planned change as harmless. A plan with any unexpected
replacement/destruction or unrelated object fails the gate.

The lead's separate allowlisted state extraction found **61 owned resource
records, serial 16**, matching the observed current image indices, old logical
database/user and scheduler. The source default `maintenance_paused=true` differs
from the actual/state scheduler enabled setting. This is a source/input mismatch
that must be represented by the reviewed planning inputs, not evidence that an
unrelated actor changed the live resource. The original state backend remains
unchanged. Do not apply defaults that accidentally pause or redeploy the old app.

New ownership is planned under `module.tasteduel_foundation` in the **same root
and backend**. Proposed distinct module addresses include
`module.tasteduel_foundation.google_sql_database.app` for `tasteduel`,
`module.tasteduel_foundation.google_sql_user.app["runtime"]` and `["migrate"]`,
`module.tasteduel_foundation.google_service_account.app["web"|"api"|"migrate"|"deploy"]`,
plus scoped module-owned IAM/secret resources. These are a planned address
contract, not resources already in state or a deployable saved plan. Preserve
`google_sql_database.app` and `google_sql_user.app` outside that module as legacy
AccessLife ownership until deliberate retirement. The release service/job
addresses are finalized only with published digests and the reviewed release plan.

**Foundation review:** new identities, scoped access, new logical DB/users/secrets,
repository/WIF preparation and required registry rights only. Preserve old
application traffic and ownership. No nonexistent app image references or routine
`-target` workaround. Database password/secret values stay ephemeral/write-only;
review saved plans privately.

**Release review:** only after real tested Taste Duel image digests are published,
prepare new services/migration job and exact origins/secret versions. A first
Cloud Run revision is not automatically no-traffic; use an authenticated/control
maintenance bootstrap or record its real allocation, then tagged no-production-
traffic candidate testing. Tags can still accept direct traffic. Traffic promotion
is a later explicit release step after external gameplay/restore/security/cost
checks; this document does not authorize it.

See the [cost review](../COST_REVIEW.md) for the refreshed gate. Historical $78.48
is not current headroom. Any missing incurred-cost evidence, unpriced overlap or
failed cumulative $80 estimate blocks provisioning even when static validation
passes.

No apply-ready saved foundation/release plan is claimed. Current cost evidence
and a safe complete-state plan must pass before the next provisioning stage.

An additional 12 read-only calls inspected exact dedicated service/secret/bucket/
registry IAM policies and an AccessLife-prefix filtered monitoring query. The web
has `allUsers` invoker; API/worker have no such resource-level grant and use their
web/task identities respectively. No matching AccessLife alert policy was returned
(no further page); the existing uptime check and billing alert are separate
resources. Inherited IAM must still be assessed using the scoped project review.
The private supplement is `.data/tasteduel-cloud-review/policy-metadata.json`.
This is a binding inventory, not an effective-access evaluation: the initial
snapshot omitted binding conditions and did not prove inherited anonymous
project access. The hardened helper preserves selected conditions on future
reads; verify complete effective policies before foundation/release grants.

## Executed runtime retirement ? 27 October, 14:09 UTC

User-authorized retirement deleted `accesslife-web`, `accesslife-api`,
`accesslife-worker`, jobs `accesslife-migrate`, `accesslife-ingest`,
`accesslife-reconcile`, scheduler `accesslife-reconcile` and queue
`accesslife-planning`. All eight returned 404 after deletion. The revision names
above are historical metadata, not currently selectable traffic targets. Registry
digests, source checkpoint, SQL/data/users, state, secrets and buckets remain the
rollback basis; no shared resource was renamed or removed.
See [retirement execution and state handling](retirement-options.md). The
remote state remains unchanged pending a reviewed full plan using forget-only
removed blocks; this is deliberate recorded drift, not an apply success.

## Executed runtime retirement ? 27 October, 14:09 UTC

User-authorized retirement deleted `accesslife-web`, `accesslife-api`,
`accesslife-worker`, jobs `accesslife-migrate`, `accesslife-ingest`,
`accesslife-reconcile`, scheduler `accesslife-reconcile` and queue
`accesslife-planning`. All eight returned 404 after deletion. Revision names
above are historical metadata, not currently selectable traffic targets. Registry
digests, source checkpoint, SQL/data/users, state, secrets and buckets remain the
rollback basis; no shared resource was renamed or removed.
See [retirement execution and state handling](retirement-options.md). The
remote state remains unchanged pending a reviewed full plan using forget-only
removed blocks; this is deliberate recorded drift, not an apply success.
