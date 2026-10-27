# State ownership and drift review

**Current update, 27 October 14:09 UTC:** explicitly authorized legacy runtime retirement is complete; shared assets remain. Original read-only findings below are historical. See [execution and reconciliation](retirement-options.md). New foundation provisioning remains blocked.

27 October 2026. The existing state was read once in memory; no raw state,
credential values or saved plan payload was printed or written. The allowlisted
metadata artifact is `.data/tasteduel-cloud-review/state-ownership.json`.

Backend remains `gs://accesslife-tfstate-project-bb13ecd8-9d67-408d-9a7/`
with prefix `accesslife/state`, object `accesslife/state/default.tfstate`.
Observed serial **16**, **61 resource/data instance records**, object generation
`1792824552399397`, last updated 24 October. Bucket bootstrap is outside this
root; do not import it or move the prefix as part of the product rename.

| Compared field | Saved ownership / observed cloud metadata | Assessment |
|---|---|---|
| Old web/API/worker resource IDs | Exact existing AccessLife service names and region | Match in selected fields; no adoption/replacement needed |
| Configured web image | `4fd3995f835d59ed0801d94ae8bdec2707953774f84880754442da2930b10346` | State/live index matches; resolved revision manifest differs legitimately |
| Configured API/worker image | `fe4be430367838a54b6f397351c3f9381c922a15ec65a8b9b597c381ae533474` | State/live index matches |
| Current traffic | Latest target, 100% for all three | Selected state/live allocation matches; rollback not rehearsed |
| Old SQL instance/database/user | `accesslife-db` / `accesslife` / `accesslife` at stable root addresses | Match; no Taste Duel objects already exist to import |
| SQL capacity/protection | 1 CPU/3.75GiB, zonal, SSD20/growth40, both protection layers enabled | Selected fields match |
| Reconcile scheduler | State `paused=false`; live ENABLED every five minutes | Match; source default `maintenance_paused=true` is an input mismatch, not proven external drift |
| Legacy labels | `app=accesslife,environment=hackathon` | Current metadata; proposed shared billing label is unapplied source change |

These checks reconcile selected ownership/cost-critical metadata only. They are
**not** a full Terraform refreshed action plan. Provider defaults/computed values,
all IAM differences, old secret-version lifecycle and runtime settings still need
full plan review with correct inputs. Service-level max instances 5 coexists with
revision-level caps 2/2/1; do not silently normalize away either setting.

New source changes add legacy SQL/DB/user `prevent_destroy` and stronger cumulative
cost preconditions. Proposed common billing label/filter and later alert window
are in-place future changes, not current cloud settings. They must not be applied
as an accidental side effect of default inputs or with an unreviewed old image.
No addresses, backend, database names, SQL passwords or service images changed.

Full foundation and release plans remain blocked by missing actual accrued
billing and incomplete executable foundation/release configuration. No `.tfplan`
is described as approved here. Historic ignored plans belong to AccessLife and
must not be reused. New ownership may only be added after review at distinct
addresses in the same root; any foreign/destructive action rejects the plan.

Final local checks passed: Google 6.50.0/Terraform 1.13.3 schema validation,
five built-in-only synthetic cost-gate plans, seven targeted metadata/source
preservation contracts, Compose configuration, Ruff, local links and scoped
Gitleaks. The source contract verifies that all baseline resource declarations
remain and the only added resource declaration is the notification budget.
These are configuration checks, not a refreshed authenticated cloud action plan.

## Authorized operational drift ? 27 October, 13:53?13:56 UTC

The user explicitly selected runtime retirement while preserving shared assets.
Scheduler `accesslife-reconcile` and empty queue `accesslife-planning` are now
PAUSED. The original scheduler state snapshot above remains historical. No
state object was edited or removed. Before any root apply, reconcile retirement
source/actions; do not recreate retired services or resume dispatch accidentally.
Partial labelled Billing Reports evidence is in the cost review; it does not
establish complete accrued attribution or approve foundation execution.

## Recorded retirement drift ? 27 October, 14:09 UTC

All eight authorized runtime resources were deleted directly and absence verified.
Current source removes twelve runtime/dependent-IAM declarations and supplies
matching `removed { lifecycle { destroy = false } }` blocks. Shared owned
addresses remain. Remote state generation is unchanged. The earlier source
preservation statement describes the pre-retirement review; current tests permit
only the exact authorized removals against pinned baseline `ef5c27c`. No full
refreshed saved plan or state reconciliation apply has occurred. Do not apply an
old checkout, which would recreate legacy runtime. The next full current-source
plan must verify only expected forget actions and gated new foundation additions.

## Recorded retirement drift ? 27 October, 14:09 UTC

All eight authorized runtime resources were deleted directly and absence verified.
Current source removes twelve runtime/dependent-IAM declarations and supplies
matching `removed { lifecycle { destroy = false } }` blocks. Shared owned
addresses remain. Remote state generation is unchanged. The earlier source
preservation statement describes the pre-retirement review; current tests permit
only exact authorized removals against pinned baseline `ef5c27c`. No full
refreshed saved plan or state reconciliation apply has occurred. Do not apply an
old checkout, which would recreate legacy runtime. The next full current-source
plan must verify only expected forget actions and gated foundation additions.
