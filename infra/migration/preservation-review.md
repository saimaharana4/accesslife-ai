# Migration preservation and destructive-change review

**Current update, 27 October 14:09 UTC:** explicitly authorized legacy runtime retirement is complete; shared assets remain. Original read-only findings below are historical. See [execution and reconciliation](retirement-options.md). New foundation provisioning remains blocked.

Reviewed 27 October 2026. This is an independent source/design review for the
Taste Duel migration. It does not authorize application, traffic, repository,
IAM, secret or database changes. Static validation is not a reviewed cloud
execution plan or a successful migration.

## Boundary and evidence

Allowed scope is the dedicated AccessLife resources in
`project-bb13ecd8-9d67-408d-9a7`, principally `asia-south1`, plus their explicitly
identified global IAM/WIF/secrets/billing metadata. PharmaGuard and other
project resources are excluded even where they share a project, billing
account or administrator. A project-wide list used to filter dedicated
identities is not permission to manage every returned resource.

Reviewed sources: the migration product contract in `ai/prompts.md`,
`infra/terraform/{main,operations,variables,versions}.tf`,
`infra/README.md`, the historical `infra/COST_REVIEW.md`, retired
`.github/workflows/cloud-release.yml`, current Docker build exclusions and
Taste Duel container/migration guides. The cloud inventory and state-address
reconciliation must be read alongside this review; this review does not infer
live ownership from source alone. Secret values, credential-history files,
raw state and saved plan payloads were not opened for this review.

## Preservation invariants

| Object | Required treatment | Destructive change to reject |
|---|---|---|
| Existing Terraform backend | Keep `gs://accesslife-tfstate-project-bb13ecd8-9d67-408d-9a7/accesslife/state`; retain versioned recovery | Empty-state bootstrap, simultaneous prefix migration and identity refactor, or managing the same object in two states |
| `google_sql_database_instance.db` | Keep physical `accesslife-db`, existing region/data and both deletion-protection layers | Replacement/resize without priced review; disabling protection for a branding change |
| `google_sql_database.app` | Keep `name = "accesslife"` at stable address, or explicit reviewed `moved` block | Changing its name to `tasteduel`, removing its block, or accepting a delete/create action |
| `google_sql_user.app` | Keep physical `accesslife` and its existing ownership until retirement | Reusing address/name input to replace it with a Taste Duel login or rotating it accidentally during planning |
| Taste Duel logical database/users | Add new independent addresses; migration owner and runtime DML principal are separate | Restoring/migrating over AccessLife; runtime superuser/DDL privileges; migration login in API runtime |
| Existing Qloo secret | Retain physical ID/version/readers until deliberate cutover/rollback expiry; new API gets only this needed reference | Printing/copying key during inventory, blanket copying optional keys, disabling legacy readers early, calling a copy a rotation |
| State/docs/backups buckets, registry | Preserve immutable legacy IDs where reuse is justified; keep data protection/lifecycle | Cosmetic replacement, `force_destroy`, shared purge, or retention shortening before evidence/rollback policy permits |
| Existing service/job/queue/scheduler resources | Preserve stable addresses and actual traffic during this read-only stage | Deleting blocks, unpausing jobs, changing images to Taste Duel, or draining/stopping production traffic now |
| Repo, WIF and deploy identity | Numeric repo/owner and exact main/environment trust; coordinated transition | Owner-wide wildcard, trusting both names indefinitely, rename before validating trust sequence, or project-wide deploy admin |

Add `prevent_destroy` on legacy database/user and shared data resources where
practical before legitimate refactoring. It is an additional guard: a removed
resource block also removes its lifecycle guard, so plan action review and
state preservation remain mandatory. Keep Cloud SQL deletion protection; a
logical-database guard is separately necessary because instance protection
does not by itself prove database/user protection.

## Foundation and release separation

The current historical root contains runtime resources with required image
inputs. It must not be pointed at unpublished or invented Taste Duel digests
to produce a supposedly complete foundation apply. Routine `-target` is not
an acceptable substitute for separating ownership.

1. Reconcile observed resources and state addresses first. Missing addresses
   require explicit import of the exact observed ID; source/state mismatches
   require a reviewed correction preserving the real deployment. A `moved`
   block renames ownership, not the cloud object. Neither operation is
   permission to recreate resources.
2. Foundation must be a complete independently reviewable plan containing
   only identities, scoped grants, new logical database/users/secrets,
   repository trust and compatible shared infrastructure. No Cloud Run
   service, migration-job execution, image placeholder, traffic change or
   legacy retirement belongs in that apply. Any split into separate state
   requires an explicit ownership handoff; never duplicate resources across
   state files.
3. Release follows published reviewed web/API digests, a successful CI SHA,
   compatible cloud migration configuration, pinned secret versions and
   verified IAM invoker boundaries. A new service's first revision cannot
   promise zero traffic simply by using `--no-traffic`; first bootstrap
   access must be restricted. A reachable revision tag is not access control.
4. Production cutover and legacy retirement each require their own later
   gate. No destructive action is implicit in an old-to-new resource map.

The historical `scripts/terraform_local.py` resolves the legacy SQL password
for every `plan`/`apply` and imports an AccessLife adapter. Do not use it for
metadata inventory or assume it is a safe Taste Duel foundation runner.
Backend-free static validation requires no secret values. Future planning
that genuinely needs write-only/ephemeral credential inputs must resolve them
in memory through a reviewed path without local files or output. Do not dump
`terraform show -json`, state or raw cloud responses into public artifacts.

## Identity and database checks before a future apply

- Web: service-local `run.invoker` on Taste Duel API only; no SQL or secret
  accessor. Public invoker applies only to the intended public web, after
  the relevant release gate. Private API must reject unauthenticated calls.
- API: Cloud SQL connector permission, only runtime database/Qloo secret
  versions and required Vertex use. It must not use migration-owner credentials
  or legacy worker tokens/tasks/ingestion roles. Shared Qloo quota controls
  must include any overlapping legacy caller or reserve that caller's usage.
- Migration: separate identity and database owner; no public entry point,
  bounded one-shot execution, no Qloo/model access unless justified. SQL
  `PUBLIC` database/schema defaults must not grant old logins access to new
  tables. Check explicit database/schema/table/sequence privileges and RLS;
  creating a Cloud SQL SQL user alone is not least-privilege proof.
- Deploy: registry writer, exact service/job developer and act-as on only
  required Taste Duel runtime/migration identities. No secret read, project
  editor/owner or unrelated service mutation.
- WIF: inspect actual numeric GitHub repository/owner IDs and provider
  mapping; constrain repository, main branch and approved environment. Verify
  keyless authentication before relying on renamed repo workflows. GitHub
  redirects do not update trust expressions.

## Rollback, retention and stop conditions

The exact observed old image digests/revisions/traffic and secret version
references are rollback inputs, not illustrative strings. Preserve those
artifacts in the reused registry; do not apply cleanup policies that remove
them during the rollback window. Old logical database/user, required secret
versions, service accounts and compatible schema stay until Taste Duel
release/recovery verification and an explicit retirement decision. AccessLife
rollback must point to the old database; Taste Duel rollback must preserve
its accepted answers, fixed challenges and immutable snapshots.

Retain both logical databases at least through the reviewed judging endpoint
of 6 November 2026, 10:15 IST and the explicit approved follow-up/rollback
window. Continued retention beyond the costed window requires a new cost
review; do not silently delete data to force the budget to pass. Backups may
outlive session clearing and should follow the documented rights/retention
policy. A restore test uses only a separately priced disposable target and
never overwrites either source database.

Block the next foundation stage if actual incurred cost cannot be reconciled,
the total forecast exceeds US$80 including tax/currency/follow-up, any
unexpected replacement/destruction or unrelated object appears, state
ownership is ambiguous, or a plan depends on unavailable images/secrets.
Alerts are notifications and label filters omit some costs. Include both old
and new resource identities plus an explicit unlabeled-cost ledger; the
historical US$78.48 forecast is not remaining headroom.

## Final source/design review

Reviewed the new `foundation-plan.md`, `release-plan.md`,
`state-and-drift.md`, `resource-map.md`, `cost-and-iam.md`, metadata helper
sources and the final Terraform source diff independently. No additional
cloud calls were made for this review.

- Legacy physical SQL/database/user names and root addresses remain stable.
  Backend/prefix, images, runtime definitions and traffic are unchanged in
  source. Three additional `prevent_destroy` guards protect the old SQL
  instance, logical database and login. No Taste Duel module or resource is
  misrepresented as implemented: the foundation module is an address contract
  for later reviewed implementation.
- The strengthened guard defaults to blocked and requires explicit accrued
  billing reconciliation, a positive budget no greater than US$80, cumulative
  total within that budget and a reviewed horizon at least 7 November 04:45 UTC.
  A later cutover/follow-up still requires a later repriced endpoint; the fixed
  earliest timestamp cannot establish that all future retention is costed.
- Proposed labels and alert source changes are unapplied. Keeping the existing
  `app=accesslife` alert while adding the shared `cost_scope` alert preserves
  transition coverage. INR6,197 is an additional notification threshold for the
  same total envelope, not a second allowance. Historical/unlabeled spend must
  still be reconciled manually. Alert end date 8 November is an exclusive
  reporting endpoint, not another authorized runtime day.
- The final plans correctly state that actual accrued cost is unavailable,
  the continuing legacy scheduler has material bounded-timeout exposure and
  no authenticated saved foundation/release plan is ready. The conditional
  US$62.52 remaining-cost adjustment is not an approved cumulative forecast.
- The validation runner does not mount ADC or the historical initialized
  backend. It extracts the real dependency-free cost guard for synthetic
  built-in Terraform tests. Those tests and backend-free schema checks can
  validate source behavior; they cannot establish a no-destroy cloud plan.
- Cloud migration host/database guards, SQL privilege bootstrap, exact runtime
  identity/model access, image publication and shared Qloo overlap remain
  explicitly future release/foundation checks. Their absence is disclosed.

No destructive replacement or unrelated ownership change was found in the
reviewed source diff. **Provisioning remains blocked**, and no apply is approved.
Missing actual accrued billing and an executable full refreshed foundation plan
remain concrete gate failures. Continue only documentation/static work until
those failures are resolved; do not bypass them with targeting or placeholder
inputs.

Lead follow-up resolved the two helper findings in source: unknown state resource
types now omit attributes/IDs/indexes, and selected IAM conditions remain explicit.
New synthetic contracts exercise both. The initial policy artifact remains a
binding snapshot rather than effective-access proof; no cloud requery was needed.
