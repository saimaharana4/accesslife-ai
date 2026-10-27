# Taste Duel foundation review plan

**Execution completed:** [verified saved-plan application and live checks](foundation-execution-2026-10-27.md). Earlier blocked prerequisites below are historical. No application service was deployed.

**Current decision:** the user approved a US$90 ceiling preserving seven backups. The refreshed conservative cumulative forecast is US$82.84; the planning cost gate passes. Earlier US$80/BLOCKED findings below are historical. See [current cost approval](cost-approval-2026-10-27.md). Foundation application and live verification are separate gates.

27 October 2026. **Design reviewed; execution blocked.** This is a resource/action
plan, not an authenticated saved `.tfplan`. The cumulative [cost gate](cost-and-iam.md)
has not passed, and no apply-ready plan is supplied. The disabled module is implemented in source; no foundation cloud resources
have been created. Runtime retirement was separately authorized and completed.

## Execution prerequisite check — 27 October 2026

Repository/WIF, credential/database and independent scope reviews all confirmed
the gate remains **BLOCKED**. No newer attributed accrued-charge report or
authenticated saved foundation plan was supplied. The instruction to execute
only after the preceding gates pass therefore permits no external foundation
mutation yet. No repository rename, remote change, WIF authentication claim,
secret creation, SQL bootstrap or apply occurred during this prerequisite check.

Connected GitHub capabilities were inspected: repository metadata reads are
available, but repository rename/update is not exposed. An authenticated REST/CLI
fallback can be used after the gates pass; no token was retrieved or printed
for this check. Target-name availability has not been newly checked and no
naming conflict is asserted. Coordinate numeric trust and verify authentication
before relying on the renamed repository; current local origin remains unchanged.

Safest next action: obtain attributable accrued Billing Reports/export, reconcile
legacy scheduling/model assumptions within the cumulative US$80 limit, then
implement and review the full foundation configuration and authenticated saved
plan. The historical ignored plans are not substitutes. Existing verification
results were reused; no cloud inventory or already-passed test was repeated.

## Preconditions and ownership

Keep the existing root at `infra/terraform`, Google provider 6.50.0 and Terraform
1.13.3, and the existing GCS backend/prefix. Add foundation ownership below
`module.tasteduel_foundation[0]` in that root after its implementation is reviewed.
Do not establish a second state claiming shared SQL, registry, buckets or WIF.
See [resource/rollback mapping](resource-map.md) and [state reconciliation](state-and-drift.md).

Legacy `google_sql_database.app`, `google_sql_user.app` and
`google_sql_database_instance.db` retain their physical names and addresses.
New source `prevent_destroy` guards supplement existing SQL deletion protection.
No `moved` or import operation is currently necessary for these observed owned
objects. A later refactor needs an explicit address-to-address `moved` block;
an owned missing object needs verified import, not recreation.

## Reviewed action set for the future full plan

| Proposed ownership | Intended action | Conditions |
|---|---|---|
| `module.tasteduel_foundation[0].google_service_account.app["web"/"api"/"migrate"/"deploy"]` | Create four Taste Duel identities | No worker, queue, ingestion, optional-provider or project-admin identity |
| `module.tasteduel_foundation[0].google_sql_database.app` | Create logical `tasteduel` on existing `accesslife-db` | No instance creation, old DB rename, old user rotation or data restore |
| `module.tasteduel_foundation[0].google_sql_user.app["runtime"/"migrate"]` | Separate `tasteduel_runtime` / `tasteduel_migrator` credentials if password login is retained | Fresh generated values go directly to Secret Manager/ephemeral write-only Terraform inputs; no payload files |
| Module-owned Secret Manager containers/versions | Runtime URL and migration URL, separate fresh credentials | Pin released versions; web/deploy get no accessor permission; no unnecessary signing secret unless implementation needs one |
| Module-owned IAM members | Selected API Qloo/runtime-secret access, migration-only DB credential, SQL connectivity, API Vertex prediction and registry writer | Resource-scoped grants wherever supported; document predefined project-level connectivity scope and enforce DB access independently |
| Existing WIF pool/provider and new deploy-SA binding | In-place numeric repository/owner claims and exact main restriction | Repository ID `1431472864`, owner ID `60200140`; preserve working authentication until replacement verified |
| Existing registry | Reuse `accesslife`, add writer only for new deploy identity | No new registry/storage service or blanket artifact cleanup |
| Existing dedicated labels/budget | Reviewed in-place shared `cost_scope=qloo-hackathon` label and combined notification coverage | Reconcile historical `app=accesslife`, new `app=tasteduel`, transition alerts and unlabeled charges separately |

`google_sql_user` creation is not proof of restricted database privileges. A
reviewed administrative bootstrap must inspect/remove unwanted inherited Cloud SQL
roles and grants, revoke inappropriate PUBLIC CONNECT/TEMP/schema creation rights
on **the new database only**, establish the migration owner and runtime DML grants,
and prove old-database data-access denial plus no runtime CREATEROLE/CREATEDB/BYPASSRLS/DDL.
If connection-level isolation also requires changing existing PUBLIC grants,
review the old-reader allowlist and compatibility explicitly before that change;
a direct user REVOKE alone cannot override privileges inherited through PUBLIC.
Check every migration against actual forced-RLS ownership: the current local
lineage must be adapted before any cloud migration. Never change the old
database/user's privileges as an incidental Taste Duel bootstrap action.

Keep existing runtime image inputs and old public URL at their observed values,
and represent the current scheduler setting explicitly. Do not set the legacy
web/API image variables to Taste Duel images. No Cloud Run product service or
image is needed in this foundation action set. First service creation and its
resource-scoped deployment permissions belong to the release bootstrap.

## Safe future execution gate

1. Obtain attributed accrued charges and review the priced scheduler/model
   adjustment; keep `billing_reconciled=false` until verified. Reprice if cutover
   or rollback extends beyond the documented window. The US$80 is cumulative.
2. Implement/review the new foundation module and a safe full-root planning path.
   The historical `scripts/terraform_local.py` resolves legacy secret values;
   it was deliberately not used for this metadata-only review.
3. Generate the full refreshed plan against the unchanged backend with legitimate
   current legacy inputs and ephemeral new credential inputs. Do not use `-target`,
   a fake image, an empty state, or a synthetic password to create an apply plan.
4. Review every action: no delete/replace on old DB/user/SQL/state/registry,
   unexpected runtime/traffic change, unknown unrelated resource or optional
   service. The scheduler and empty queue were explicitly authorized and paused on
   27 October. Retain that state; do not restart legacy dispatch as a side effect.
5. Save that actual plan privately only after all gates pass. A later separately
   authorized foundation stage may apply that exact reviewed plan and verify WIF,
   DB privileges and grants. This document grants no apply authority.

Repository renaming is a separate deliberate action in the next stage: first
check name availability, coordinate numeric trust, preserve history/tags and
verify authentication. No repository or WIF change occurred here.

## Foundation source prepared, not applied ? 27 October

The disabled-by-default module now exists in `infra/terraform/modules/tasteduel-foundation`,
with root ownership `module.tasteduel_foundation[0]`. It uses separate ephemeral
write-only credentials, preserves the old SQL addresses, and creates no product
service/job or public binding. Numeric repository/owner, main and
`foundation-review` environment trust is conditional on the reviewed enable flag.
The manual auth-only workflow is source preparation, not verified authentication.
No saved authenticated foundation plan exists. Database privilege bootstrap,
effective IAM verification and cumulative billing reconciliation remain open.
