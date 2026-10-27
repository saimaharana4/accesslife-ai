# Taste Duel cumulative cost and identity review

**Current decision:** the user approved a US$90 ceiling preserving seven backups. The refreshed conservative cumulative forecast is US$82.84; the planning cost gate passes. Earlier US$80/BLOCKED findings below are historical. See [current cost approval](cost-approval-2026-10-27.md). Foundation application and live verification are separate gates.

Reviewed **27 October 2026**; inventory cutoff **17:21 IST**. Scope: dedicated AccessLife
metadata in `project-bb13ecd8-9d67-408d-9a7`, Mumbai (`asia-south1`) plus its
scoped billing/WIF configuration. This review made no cloud mutations, Qloo
requests or model calls. PharmaGuard resources and charges are excluded.

**Gate: BLOCKED (not passed).** A partial actual labelled billing subtotal has
now been obtained; full unlabelled attribution and late-arriving usage remain
unreconciled. The obsolete scheduler and empty queue were explicitly authorized
and paused at 13:53?13:56 UTC on 27 October. Historical
`US$78.48` is an estimate, not measured expenditure or fresh headroom. Keep
`cost_review_passed=false`; no foundation apply is approved by this document.

## Evidence and price basis

Private ignored metadata is in
`.data/tasteduel-cloud-review/{inventory,cost-iam-metadata,cloud-run-prices}.json`.
Only resource/account metadata, IAM policies and public catalogue prices were
read; no secret payload, state payload, billing payment profile or other
application's resource details were collected here.

The current Cloud Billing Catalogue was fetched in USD and INR on 27 October:
SQL service `9662-B51E-5089`, 20,258 SKUs examined per currency. Exact Mumbai
matches (on-demand, no committed-use or shared-account free-tier assumptions):

| Item | Verified SKU | USD rate |
| --- | --- | ---: |
| PostgreSQL Enterprise zonal CPU | `DF80-E0D1-CCE3` | 0.0496 / vCPU-hour |
| PostgreSQL Enterprise zonal RAM | `72C1-62A1-2C8B` | 0.0084 / GiB-hour |
| PostgreSQL zonal standard SSD | `42A1-880A-9B0F` | 0.204 / GiB-month |
| SQL backups in Mumbai | `D737-A9D2-80AB` | 0.096 / GiB-month |
| Cloud Run request CPU | `4856-B847-F1EB` | 0.000024 / vCPU-second |
| Cloud Run request memory | `02A2-9231-36A6` | 0.0000025 / GiB-second |
| Cloud Run job CPU | `5214-2CF1-0F55` | 0.000018 / vCPU-second |
| Cloud Run job memory | `FEB8-83AE-2E8C` | 0.000002 / GiB-second |

Catalogue endpoint: `GET https://cloudbilling.googleapis.com/v1/services/{service}/skus?currencyCode=USD`
(repeat for INR; this reads tariffs, not actual account usage).
[Cloud SQL pricing](https://cloud.google.com/sql/pricing) and
[Cloud Run pricing](https://cloud.google.com/run/pricing) explain the pricing
models. Jobs have a **one-minute billing minimum**, even when the observed
execution lasts about 25 seconds.

The currently pinned model remains `gemini-3.1-flash-lite` at `global`, whose
existing project/IAM smoke is recorded in the maintained capability evidence.
Current published standard global text rates are **US$0.25/M input tokens and
US$1.50/M output/reasoning tokens**. No model was invoked in this review; old
project access is not proof that a future `tasteduel-api` identity has access.
[Model prices](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing),
[deployment locations](https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/locations).
The model endpoint is global; Mumbai runtime does not promise India-only model
processing or Qloo data residency.

The same CPU SKU is INR 4.761041999 versus USD 0.0496, giving the catalogue
conversion **INR 95.98875/USD**. This is a tariff ratio rather than a bank FX
quote. Use an **18% tax reserve and an additional 5% FX/tariff contingency** until
invoice treatment and current settlement conversion are reconciled; neither is
a claim about the user's tax registration.
[India tax documentation](https://docs.cloud.google.com/billing/docs/resources/vat-overview#india).

## Actual accrued costs: partial billing evidence, attribution incomplete

The linked billing account is open and INR-denominated; its current AccessLife
budget can be read with the explicit quota project. A metadata-only BigQuery
dataset discovery found no accessible `billing`/`cost`-named dataset in this
project and no further page. This does **not** establish that no export exists
in another authorized location, or that all possible dataset names were ruled
out. No usage query or export was created. The Budget API returns configuration,
not the actual accrued subtotal. No previous billing-cost export was present in
the reviewed safe repository evidence.

Required before approval: an authorized Billing Reports CSV or existing export
with usage dates from 24 October through the review cutoff, project filtering,
`app=accesslife`/`app=tasteduel`, detailed dedicated resource/SKU attribution where
available, credits separately shown, currency/conversion, tax, and late-arriving
usage reconciliation. Manually attribute dedicated unlabeled Vertex, network,
registry, secret and job charges; never count the unrelated application's total
as AccessLife or subtract an assumed amount. Actual-spend access remains a
specific missing gate, not permission to invent a number.
[Billing export contents and limitations](https://docs.cloud.google.com/billing/docs/how-to/export-data-bigquery).

For orientation only, observed SQL activation from
`2026-10-24T05:06:24.292Z` to the inventory cutoff
`2026-10-27T11:51:16.468799Z` is 78.7478 hours. At the current 1 vCPU / 3.75 GiB
rate, **US$6.3864** is its tariff-based compute estimate. The reconcile job's
932 executions imply at least **US$1.2302** of gross allocated job compute at
the one-minute minimum and 1 vCPU / 2 GiB configuration, before free-tier
accounting. These are incomplete estimates, **not actual accrued spend**;
duration distributions, retries, other services, past prices and credits are
not established by these metadata.

## Reviewed time window and conditional forecast

Minimum availability ends **6 November 2026, 10:15 IST**
(`2026-11-06T04:45:00Z`): 232.8954 hours after the inventory cutoff.
The priced base case adds **24 hours of follow-up**, ending **7 November,
10:15 IST**: 256.8954 hours remaining. Retaining old logical data for seven days
after a later cutover may extend this window; reprice that extension before
cutover. Retention in the same running instance adds storage, not a second
instance; it does not eliminate continued instance costs.

The following is a **conditional adjustment**, not a passed forecast. It requires
an authorized pause of legacy scheduled work within 24 hours, no continuing
legacy model traffic, bounded traffic, and refreshed actual spend. None of
those cloud changes occurred here.

| Remaining item through 7 November 10:15 IST | Pre-tax USD | Explicit basis |
| --- | ---: | --- |
| Existing dedicated SQL compute | 20.83 | 256.8954h × (0.0496 + 3.75 × 0.0084); ALWAYS, ZONAL, no HA |
| SSD growth reserve | 2.82 | Charge full 40GiB ceiling throughout remaining window; current allocation is 20GiB |
| Backup reserve | 9.28 | Conservative 7 × 40GiB upper planning quantity, not measured backup size; no dedup credit; 744h catalogue month |
| New web/API request compute | 8.04 | ≤250,000 vCPU-s, ≤800,000 GiB-s and ≤100,000 requests total; no free-tier credits |
| Vertex | 3.60 | 11 daily windows, ≤100 calls/day, ≤1M input tokens/day plus ≤51,200 output tokens/day as conservative separate bounds |
| Registry and dedicated GCS/state | 2.00 | Small images; current dedicated registry about 0.66GiB; ≤5GiB added images/objects; local builds |
| Secrets, network, logging, alerts/scheduler/tasks tail | 3.00 | Small demo envelope; no VPC connector/NAT; no paid external artwork provider assumed |
| Logical restore and one migration job | 0.50 | Bounded disposable logical restore on shared instance or short local target; **not** a managed-instance restore acceptance claim |
| Legacy scheduled overlap, first 24h only | 0.38 | 288 executions × 60s minimum × (0.000018 + 2 × 0.000002); observed-pattern assumption, not a worst-case cap |
| **Conditional remaining subtotal** | **50.46** | Unrounded component sum rounded upward |
| **Tax + 5% FX/tariff reserve** | **12.06** | subtotal × 1.18 × 1.05 |
| **Conditional remaining total** | **62.52** | Must add all actual AccessLife incurred costs |

Using unrounded quantities except the upward model allowance gives a remaining
usage estimate of US$50.4533 and tax/FX-inclusive US$62.5117. A conservative
rounded **US$62.52** leaves only **US$17.48 tax/FX-inclusive** of the US$80 total
for actual accrued costs. If actual incurred spend is supplied pre-tax/pre-FX,
its equivalent available allowance is about **US$14.11**. Do not add estimated
accrued SQL/job charges and then label the result an actual-spend pass.

The minimum 6 November endpoint reduces SQL compute by US$1.9464 and reduces
SSD/backup exposure too; it does not remove follow-up or rollback obligations.
An extra day with the conservative 40GiB SSD and 280GiB backup reserve adds
about US$3.08 pre-tax before runtime/model traffic. Do not silently shorten the
judging requirement to fit a target.

### Current-state risk and priced adjustments

`accesslife-reconcile` is **ENABLED every five minutes**, despite the source's
paused-by-default control. At one-minute minimum allocations it continues at
about **US$0.3802/day** gross (US$4.0692 to the follow-up endpoint). Its actual
configuration permits 300-second tasks with one retry: a scheduling-bound
600-second allocation case is about **US$3.8016/day**, or US$40.6922 over the
remaining window, before possible overlapping retries/other traffic. It is not
honest to promise that all future tasks will match the last successful 25s run.
With this timeout/retry exposure substituted into the conditional table, the
remaining envelope alone is approximately **US$112.46 tax/FX-inclusive**, before
any accrued charges. The current unchanged setup therefore cannot pass US$80.

Priced next-stage adjustments: pause only the dedicated legacy scheduler after
review (no change here), retain jobs/images/data for rollback without routine
execution, enforce new services' min instances 0 and bounded request concurrency,
and keep 100 Vertex calls/1M conservative token admission per day or lower.
Pausing after one day avoids about US$3.69 of the remaining minimum-pattern
legacy compute; the timeout case avoids much more. One additional always-on SQL
instance would add roughly US$20.83 compute plus storage/backups over this window
and is rejected. Managed restore requiring a temporary second instance must be
priced separately before execution; the US$0.50 logical-restore allowance does
not authorize it. Added actual legacy model activity or extra build/cloud
egress needs a new line, not an implicit zero.

Use project-owned title cards; no TMDB/other optional paid data expense is
required. Qloo event-key monetary quota/terms are not established by GCP
billing; request ledgers remain bounded and separate from dollars. No
unpublished zero-dollar provider contract is assumed.

## Alert coverage design

Observed existing alert: `AccessLife hackathon USD80 alerts`, INR **6,507**,
custom period 24 October–6 November, thresholds 50/75/90%, project number
`902056825143`, **only `app=accesslife`**. No measured spend is in that response.

The Budget API permits only **one label and one value**, so
`app=[accesslife,tasteduel]` is invalid. Preserve the legacy alert and prepare a
separate `app=tasteduel` alert, with the same cumulative-envelope interpretation;
these are overlapping notifications, **not two US$80 spending allowances**.
For improved combined coverage, add a stable `cost_scope=qloo-hackathon`
label to both sets only as an explicitly reviewed in-place change and maintain
the old alert through the transition. A common-label alert still misses
non-propagating/unlabeled usage; reconcile it manually. Do not broaden to all
project usage and thereby include PharmaGuard. Extend the reviewed end date
through follow-up, and reconvert the subtotal threshold from the current INR
catalogue ratio with the agreed reserves. Existing alert amounts/time filters
have **not** been changed. A future exclusive end date of 8 November can cover
the reviewed 7 November endpoint; an alert filter's later end date does not
authorize another unpriced day of runtime.

The proposed source now preserves `google_billing_budget.accesslife` with its
`app=accesslife` filter and adds `google_billing_budget.tasteduel_migration` for
the shared `cost_scope` label. Both source end dates are 8 November; neither
change is applied. The new notification subtotal is conservatively floored to
INR6,197 (`80 / 1.18 / 1.05 * 95.98875`), pending actual reconciliation before
apply. It is a notification threshold, not an approved second budget or a cap.
[Budget label restrictions](https://docs.cloud.google.com/billing/docs/reference/budget/rest/v1beta1/billingAccounts.budgets),
[alert behavior](https://docs.cloud.google.com/billing/docs/how-to/budgets).

## IAM and repository trust

All six legacy SAs exist and have their legacy display names: web, api, worker,
ingest, task, deploy. Project IAM bindings inspected only for `accesslife-*`:
API/worker have `roles/aiplatform.user`; API/worker/ingest have
`roles/cloudsql.client`; API/ingest have `roles/cloudtasks.enqueuer`.
Deployment can act as the four runtime identities; API/ingest can act as the
task identity. Do not copy legacy Tasks/worker/ingest permissions to Taste Duel.

The global `accesslife-github` pool/provider is ACTIVE. Actual current condition
matches repository string `saimaharana4/accesslife-ai` and `refs/heads/main`;
mapping is only `google.subject` and `attribute.repository`. Deployment-SA WIF
binding uses that exact repository-name principal set. A rename without trust
coordination would break authentication. Read-only GitHub metadata verified
numeric repository ID **1431472864**, owner ID **60200140**, public/main.
These IDs are stable trust inputs, not secrets.

Prepare in-place mapping of `attribute.repository_id` and
`attribute.repository_owner_id`; require both verified IDs and main branch in
the provider condition, and bind only the exact numeric repository principal
set to the dedicated deploy SA. If a protected environment is introduced,
validate its OIDC subject and approval policy before requiring it; do not assume
one exists. Preserve existing authorized deploy authentication until its
replacement is tested; no name rename or WIF update occurred in this review.
[Numeric GitHub claims and security guidance](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines).

| New identity | Minimum intended boundary |
| --- | --- |
| `tasteduel-web` | Invoke only `tasteduel-api`; no Secret Manager, SQL, Vertex, Qloo or deploy access |
| `tasteduel-api` | Cloud SQL connectivity plus DB runtime DML/RLS principal; selected runtime DB/session/Qloo secret versions; Vertex use; no DDL/migration owner, IAM admin or queue permissions |
| `tasteduel-migrate` | Cloud SQL connectivity and distinct migration-owner credential on **only `tasteduel`**; no Qloo/model/old DB rights |
| `tasteduel-deploy` | Exact repository WIF; dedicated registry writer; actAs only the new runtime/migration SAs; service/job-scoped update/deploy permissions; no project Owner/Editor/IAM/SQL admin |
| Administrative foundation executor | Separate explicitly reviewed local/IAM authority; no persistent broad GitHub role |

Cloud SQL IAM client is project-scoped in the common predefined grant; constrain
the connection-name configuration and PostgreSQL credentials separately. It
does not itself grant SQL data privileges. Foundation bootstrap must establish
new DB/user under existing administrative access, then verify migration owner
versus runtime DML, forced RLS and old logical-database denial. Cloud Run resource
creation cannot be magically scoped to a nonexistent service: create reviewed
foundation/bootstrap resources via the administrative executor, then grant the
release identity only those service/job resources rather than project-wide
administrator rights. Do not grant secret access merely to build images.

Retain shared `accesslife-qloo-api-key` name/version temporarily with only the
new API reader added in a later reviewed plan; web/migration/deploy get no
access. Pin versions at release, preserve old legitimate readers until rollback
expiry, and reconcile the legacy runtime's provider quota bypass before overlap.
Copying the value into a new secret is not key rotation. New DB/runtime/migration
and signing secrets belong in Secret Manager with payloads written directly by
the reviewed foundation path, never source/plan payload files or committed state.

## What unlocks the foundation stage

1. Obtain and reconcile actual attributed accrued spend; no provider payloads or
   payment details are needed.
2. Reconcile enabled scheduler drift and explicitly price its authorized pause,
   overlap and legacy model access; keep unrelated resources untouched.
3. Confirm conservative cumulative total including tax/FX through follow-up is
   ≤US$80; otherwise present reduced bounded traffic/retention alternatives with
   required availability preserved.
4. Review a complete non-destructive foundation plan, correct stable legacy
   DB/user ownership, numeric WIF trust and separate runtime/migration privileges.
5. Only a later authorized stage may apply. Release/service plans wait for actual
   immutable image digests and are independently reviewed.

## Billing and retirement update ? 27 October 2026

Read-only Cloud Billing Reports, custom usage dates **24?27 October 2026**,
filter **label `app=accesslife`**, displayed:

| Service | Usage cost INR | Credits INR | Displayed net INR |
|---|---:|---:|---:|
| Artifact Registry | 0.57 | -0.57 | 0.00 |
| Secret Manager | 0.76 | -0.76 | 0.00 |
| Cloud Run | 109.47 | -109.47 | 0.00 |
| Cloud SQL | 552.59 | -552.59 | 0.00 |

The report summary displayed **663.40 INR credits** and **0.00 INR filtered
subtotal**. Rounded service rows sum to 663.39 INR; do not infer greater precision.
This proves actual labelled usage/credits only, not complete accrued AccessLife
cost or future credit availability. The project was console context; a separate
project filter was not verified. Unlabelled model/network/bucket/build usage,
reporting lag, date-boundary treatment and tax remain to be reconciled. No
unrelated workload subtotal is attributed to AccessLife. No payment details or
secret payloads were read. Private evidence records only these allowed figures.

The existing **US$62.52** remains a historical conditional remaining forecast
from the 17:21 IST cutoff, not a refreshed cumulative approval. Scheduler and
queue pauses now establish a cost-reducing operational change; do not subtract
unmeasured savings or assume future credits. SQL/storage/backups still accrue.
New foundation resources remain disabled pending attribution and a reviewed full
saved plan. Runtime retirement is separately authorized and does not require
waiving or falsifying the new-provisioning cost gate.
