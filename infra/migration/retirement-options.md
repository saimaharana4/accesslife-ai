# Dedicated AccessLife retirement options

27 October 2026. The user explicitly authorized retiring obsolete services,
scheduler, jobs and queue while retaining shared SQL, registry, state, secrets
and rollback data. This authorization does not waive the cumulative cost gate
or authorize destructive changes to those preserved assets.

## Verified execution so far

- Scheduler `accesslife-reconcile`: ENABLED ? PAUSED, verified at 13:53:56 UTC.
- Queue `accesslife-planning`: zero tasks/no further page immediately before
  pausing; RUNNING ? PAUSED, verified during the 13:56 UTC drain check. No purge.
- Exact maintenance-job execution listings: migrate 1, ingest 1, reconcile 956;
  zero unfinished executions and no truncated listing.
- At **14:09:12 UTC**, deletion completed for all three services, all three
  maintenance jobs, reconcile scheduler and planning queue; each exact resource
  GET returned 404 after deletion. No new foundation apply, repository rename,
  secret payload access, shared-data mutation or Taste Duel public traffic occurred.

Private metadata evidence: `.data/tasteduel-cloud-review/retirement-progress.json`
and `retirement-drain-metadata.json`. Queue/job quiescence does not prove all
database-backed legacy runs settled. Scheduler/queue must not be resumed by a
subsequent Terraform plan. The reviewed source change removes runtime declarations and dependent Run IAM,
with twelve explicit `removed` blocks (`destroy=false`) so a later apply forgets
old ownership without recreation. Remote state has not been edited or applied.
The user has already authorized that scope; no repeated scope approval is needed.

Deleting or renaming a resource does **not** remove charges already incurred.
The cumulative US$80 gate still needs attributed Billing Reports/export and
late-arriving usage reconciliation. Labels do not rewrite historical bills.
The [cost review](cost-and-iam.md) remains **BLOCKED**; its US$62.52 conditional
remaining forecast is not measured expenditure or an approved budget.

## Authorized retirement rationale and historical alternatives

The scope above is authorized. Remaining deletions need a separately reviewed
state-aware plan and verification of current accepted work before execution. They are
not bundled into the foundation changes.

| Dedicated resource | Possible later action | Required preservation/verification | Financial implication from recorded review |
| --- | --- | --- | --- |
| Scheduler `accesslife-reconcile` | Pause scheduled dispatch | Record current config; verify no accepted execution still depends on continuing reconciliation; retain job/image/data for recovery | Avoids future routine invocations, not past charges. Recorded minimum is about US$0.3802/day gross; 300-second task plus one retry case about US$3.8016/day. Neither is measured invoice spend |
| Queue `accesslife-planning` | Pause dispatch, then drain accepted work under a reviewed procedure | Snapshot count was zero but is stale; inspect only this queue immediately before an authorized pause; do not purge accepted tasks | Removes future dispatch only after producers stop; no new savings amount established |
| `accesslife-ingest`, `accesslife-reconcile`, `accesslife-migrate` jobs | Stop invoking obsolete jobs; retain definitions initially | Disable their callers, preserve configs/images and identify active executions; do not cancel accepted work incidentally | Idle job definitions are not the recurring execution cost; no extra quantified saving claimed |
| `accesslife-worker` | Retire service after producer/drain checks and accepted-run resolution | Preserve digest/config and required credentials until rollback expires | Scale-to-zero/idle service deletion is not an always-on SQL saving |
| `accesslife-web`, `accesslife-api` | Retire old public/private runtime only after an explicit product availability/cutover decision | Capture IAM, revisions, traffic and rollback digests already in resource map; ensure no live users/runs are stranded | Runtime retirement is authorized; accepted-work and state reconciliation remain; no unmeasured saving asserted |

The existing recorded inventory is reused. A narrow just-before-change check is
necessary for mutable queue/execution state only if an operation is authorized;
it is not a reason to repeat the full inventory now.

## Preserve shared physical infrastructure and rollback assets

| Resource or ownership | Disposition |
| --- | --- |
| `accesslife-db` SQL instance | Reuse for new `tasteduel` logical DB. Do not rename, replace, delete, resize or create a second always-on instance during foundation work. Current compute/storage/backups continue to cost money |
| Old `accesslife` logical database and user | Preserve exact stable root Terraform addresses and physical names, with `prevent_destroy`. Create Taste Duel at new addresses. Database deletion is irreversible without a proven compatible restore |
| `postgres` database/user | Administrative/system boundary; no adoption, deletion or privilege changes |
| `accesslife-tfstate-…/accesslife/state` | Preserve backend, prefix, state versions and lock ownership. No simultaneous state migration or fresh empty state |
| Existing `accesslife` registry | Reuse physical ID and retain exact rollback manifests/digests; no blanket package deletion |
| Docs/backups buckets | Preserve until source-retention and backup/restore review; do not bulk copy or erase. Live objects, versions and soft-deleted objects can continue accruing costs |
| `accesslife-qloo-api-key` version 1 | Preserve shared pinned reference and old readers through rollback. New API-only grant may be reviewed. Copying the same key under a new name is not provider rotation |
| Old DB URL/password/worker token | Retain while old runtime or rollback depends on them. Never read payloads merely to inventory or rename. Revoke only after dependency and recovery review |
| Old SAs and WIF | Coordinate numeric repository trust before rename; preserve current legitimate access until tested replacement exists. Remove only explicitly identified obsolete grants later |
| PharmaGuard and unrelated project resources | Outside every action and plan boundary; never delete, relabel, import or include their spend as AccessLife |

SQL, buckets and secrets do not support a harmless in-place branding rename of
their IDs. Display-name/label updates differ from replacement. Terraform address
refactors need explicit `moved` blocks or verified imports for legitimately
unowned existing objects; never change the old database resource's `name` to
manufacture the new database.

## Irreversible operations and recovery prerequisites

Deleting logical data/users, SQL instances, secret versions, image manifests,
state versions or backup objects; purging tasks; and revoking shared readers can
break recovery or destroy accepted work. None is approved in this decision record.
Before a separate retirement decision require a scoped resource list, current
dependencies, compatible backups/exports, demonstrated restore, retained image
digests/config and an exact reverse/recovery procedure. Current metadata reports
three successful automated backups, seven-backup retention and **no PITR**; that
does not establish a tested restore or recovery of an individually deleted DB.

Existing proposal retains old logical DB/user and recovery assets for at least
seven days after verified cutover and no earlier than 6 November 2026 10:15 IST.
A 31 October cutover extends that to 7 November; later cutover needs repricing.
No automatic deletion follows the date. Required source-permission expiry must
be handled separately; anonymous-session clear does not rewrite backups.

## Next safe action

Complete attribution of accrued charges beyond the observed labelled subtotal,
then recalculate the cumulative forecast. Prepare the explicit state-aware
runtime retirement action set; preserve all shared assets and rollback digests.
Review the complete saved foundation plan separately. No resource
deletion can substitute for that billing evidence. Foundation execution and
image-dependent public release remain separate, blocked gates.

## Completion and remaining boundaries

Execution evidence: `.data/tasteduel-cloud-review/retirement-execution.json`.
A post-change ten-GET metadata check at 14:09:36 UTC confirmed existing SQL
instance/old database, registry, state object, four secret containers and both
private buckets remain present. State object generation remains
`1792824552399397`. No SQL/user/grant/secret-version mutation was requested.
No assertion is made that every in-flight legacy HTTP request completed before
shutdown; persistent rollback data remains, and old application availability ended.

Rollback requires an explicit reviewed redeployment from the preserved checkpoint
tag and recorded immutable digests/config; deleted revisions are not retained
Cloud Run traffic targets. Queue names may have a provider reuse delay; do not
promise instant identical-name recreation. Existing uptime monitoring still
points at the retired web URL and is intentionally unchanged by this scope.
The historical root must not be applied; current source must be used and its
full plan reviewed before any state reconciliation/new provisioning.

Local verification: 16 targeted contracts, Ruff, backend-free Terraform schema, five synthetic cost-gate plans, Compose configuration and scoped Gitleaks passed. These do not prove an authenticated full foundation plan, live SQL role isolation, WIF authentication or successful cloud release. No changes were staged, committed or pushed in this operation.
