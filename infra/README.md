# Taste Duel infrastructure review

**Foundation execution passed:** reviewed saved plan applied; repository rename, keyless auth, database privileges and scoped secrets verified. Taste Duel services/public traffic remain undeployed. [Verified execution record](migration/foundation-execution-2026-10-27.md).

**Current decision:** the user approved a US$90 ceiling preserving seven backups. The refreshed conservative cumulative forecast is US$82.84; the planning cost gate passes. Earlier US$80/BLOCKED findings below are historical. See [current cost approval](migration/cost-approval-2026-10-27.md). Foundation application and live verification are separate gates.

The obsolete AccessLife runtime was retired with explicit authorization. Shared
SQL/data, registry, state, secrets and rollback assets remain. Current foundation
verification does not authorize public traffic or a release without image review.

- [Resource inventory, actual rollback digests and migration map](migration/resource-map.md)
- [Current cost, assumptions and IAM/WIF review](migration/cost-and-iam.md)
- [State ownership and selected-field drift reconciliation](migration/state-and-drift.md)
- [Foundation resource/action plan](migration/foundation-plan.md)
- [Separate image-dependent release plan](migration/release-plan.md)
- [Independent preservation review](migration/preservation-review.md)
- [Executed runtime retirement](migration/retirement-options.md)
- [Verified keyless authentication](migration/keyless-auth-check.md)

The target is public `tasteduel-web`, private `tasteduel-api`, one migration job
and a new logical `tasteduel` database on existing `accesslife-db`. Keep the old
logical database/user, registry and state IDs. No new always-on SQL instance,
queue, worker, embeddings or ingestion service is needed.

## Read-only review commands

```powershell
uv run --project runtime/python --frozen python scripts/tasteduel_cloud_inventory.py
uv run --project runtime/python --frozen python scripts/tasteduel_cloud_policy_review.py
uv run --project runtime/python --frozen python scripts/tasteduel_state_review.py
uv run --project runtime/python --frozen python scripts/tasteduel_infra_validate.py
```

Metadata tools use ADC in memory and never resolve secret payloads. The state
reader holds the known state in memory and saves only allowlisted ownership
metadata. Outputs stay ignored under `.data/tasteduel-cloud-review`. The last
command validates Terraform 1.13.3/Google 6.50.0 without backend/ADC, tests the
actual cost guard with five synthetic built-in-only plans, and checks Compose.
It is not a refreshed cloud plan. Do not use the historical wrapper below for
this metadata review: its plan path resolves legacy secret values/local controls.

Actual incurred charges are missing. Conditional remaining cost is US$62.52
through 7 November 10:15 IST, leaving US$17.48 for incurred cost, assuming legacy
scheduling stops within 24 hours and no further legacy model traffic. The current
enabled scheduler's timeout/retry exposure can exceed the whole envelope before
accrued costs. See the cost report for the priced adjustment and missing evidence.

Source-only guards now require reconciled cumulative billing and the full priced
horizon; defaults block approval. Old SQL/DB/user have `prevent_destroy`. Proposed
shared `cost_scope=qloo-hackathon` labels and an additional INR6,197 notification
budget preserve legacy alert coverage; none is applied. Alerts are not caps or
separate allocations. Historical/unlabelled charges still need manual attribution.

Full saved foundation/release plans remain pending. Current cloud database guards,
least-privilege bootstrap, new-identity model access, external gameplay, restore,
expiry cleanup and human evaluation are distinct remaining gates. Recorded ready
revisions are rollback targets, not a new rollback rehearsal. Keep data/images/
required readers through the explicit rollback period; retaining recovery does
not require obsolete scheduled execution to continue.

## Historical AccessLife operations — recorded 24 October 2026

The following is retained recovery context. Its rollout/ingestion commands are
not the Taste Duel release procedure and must not be run as part of this review.

The current deployment is scoped to project `project-bb13ecd8-9d67-408d-9a7`, region `asia-south1`. Existing unrelated resources are outside this state. See the dated [cost review](COST_REVIEW.md) and [project memory](../ai/memory.md) for measured outcomes. Static validation alone is not deployment proof.

## Credentials and state

Secret Manager holds `accesslife-qloo-api-key`, `accesslife-db-password`, `accesslife-database-url` and `accesslife-worker-token`. Qloo is readable by the worker identity; database/worker credentials are scoped to the API, worker and maintenance identities. The web and CI identities have no secret accessor grants. Optional providers remain unconfigured until rotated credentials are supplied through separate Secret Manager references.

Vertex uses IAM/ADC. CI uses GitHub WIF restricted to this repository's `main` branch. No service-account keys are created. The deploy identity can update only AccessLife services/jobs and write its image repository; it does not administer existing unrelated services or Terraform infrastructure.

Terraform state is in `gs://accesslife-tfstate-project-bb13ecd8-9d67-408d-9a7/accesslife/state`, with uniform access, public-access prevention and versioning. The state bucket is a deliberately bootstrapped prerequisite outside the module. Database password inputs are ephemeral and SQL/secret provider fields are write-only. Never save credentials in `*.tfvars`, plan files or output. Keep state private even without password payloads.

`scripts/terraform_local.py` runs pinned Terraform in a disposable container, mounts existing ADC read-only and resolves the SQL password directly from Secret Manager. It supports Windows local administration. Explicitly supply current image digests, canonical public URL, cost gate and maintenance state as `TF_VAR_*` environment values. Terraform's cost gate is false and maintenance is paused by default. Nonsecret `.env.cloud` controls may specify reviewed digests/URL/maintenance state; the wrapper never reads cost approval from that file. It discovers the linked billing account privately and requires a reviewed `budget_alert_units` in the account currency.

```powershell
uv run python scripts/terraform_local.py init -reconfigure `
  '-backend-config=bucket=accesslife-tfstate-project-bb13ecd8-9d67-408d-9a7' `
  '-backend-config=prefix=accesslife/state'
# Validate without reading/applying infrastructure:
docker run --rm -v "${PWD}/infra/terraform:/work" -w /work hashicorp/terraform:1.13.3 validate -no-color
```

For a fresh clone's static CI validation, initialize with `-backend=false` first. A real plan reads the remote state and requires ADC. Quote native arguments containing `=` on Windows. Review every plan for foreign resources and deletion/replacement actions. Do not use routine resource targeting; the initial registry/SQL bootstrap preceded runtime-image publication, then a complete plan reconciles the module.

## Rollout order

1. Recheck the incremental forecast through the judging window. Stop provisioning if it exceeds US$80. Maintain daily usage review; alerts are notifications, not spending caps.
2. Build/test images; publish immutable revisions to AccessLife Artifact Registry. Use their digests for Terraform rollout.
3. Apply the reviewed AccessLife-only plan. API and worker require IAM; only web is public. Cloud SQL has no authorized external networks; Cloud Run uses the managed encrypted socket attachment.
4. Execute `accesslife-migrate`, then `accesslife-ingest`. Migrations create PostGIS, vector and application tables. The image contains a pinned licensed CPU embedding model, so runtime inference does not download it.
5. Confirm public web readiness, session isolation, a live Qloo-backed local plan, SSE, replanning, multi-city edits and unauthorized private-service rejection.
6. Set `maintenance_paused=false` and apply that reviewed change after the smoke checks. The five-minute reconciliation job recovers queued/expired executions, rotates stale task-name reservations within bounded attempts and cleans expired sessions/cache/permits/quotas.
7. Record actual URLs, revisions and verification in memory; update future Terraform inputs to match the released images and canonical URL. A manual release workflow is available, with WIF-only mode by default. Run application CI before a deployment dispatch.

```powershell
gcloud.cmd run jobs execute accesslife-migrate --project project-bb13ecd8-9d67-408d-9a7 --region asia-south1 --wait
gcloud.cmd run jobs execute accesslife-ingest --project project-bb13ecd8-9d67-408d-9a7 --region asia-south1 --wait
```

## Runtime and recovery

Three planning leases globally, five provider permits/run and twelve overall bound work. Each execution is capped at 30 seconds; expired leases are reclaimable, with at most three execution attempts. Cloud Tasks dispatch reservations persist before enqueue; retries reuse their names and reconciliation rotates stale names to avoid task tombstone stranding. Generation fallback never changes factual eligibility. Model calls are limited to 35/day in the reviewed cloud configuration.

Cloud SQL retains seven scheduled backups. Local `scripts/restore_smoke.py` exports a consistent snapshot, restores a disposable database and checks table counts/extensions; it does not establish a successful Cloud SQL backup restore. Cloud restore acceptance must be separately recorded. Backups can retain deleted personal records until expiry; never call session clearing a backup rewrite.

Rollback application services to the last known-good image digest after checking schema compatibility. Migrations must remain backward compatible; do not downgrade or drop production data to make a rollback pass. For a provider key, add a new Secret Manager version and restart its readers/revisions; caches and injected values do not automatically refresh. Database rotation also requires changing the SQL password and URL together, bumping `password_wo_version` / `secret_data_wo_version`, then rolling API and worker revisions. A new Secret Manager version alone does not rotate the SQL user. Drain queued tasks before changing the worker token, because queued task headers retain the old token.

Keep services accessible through 5 November and required judging follow-up. Extending that window requires a new forecast. Teardown is an explicit maintenance action: preserve/verify a private backup, pause jobs, stop public traffic and remove runtime resources. SQL deletion protection must be removed separately only when destruction is intended. Never run a project-wide delete or modify unrelated workloads. Local `docker compose down` retains its volume; local volume deletion is a separate destructive choice.
