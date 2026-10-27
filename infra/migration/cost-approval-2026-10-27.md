# Foundation cost approval — 27 October 2026

**Planning cost gate: PASS under the user-approved US$90 ceiling.** The user
explicitly raised the former US$80 ceiling while preserving the seven-backup
policy. This approval is separate from saved-plan review, foundation application
and public release. It does not authorize a second SQL instance.

## Actual billing evidence and conservative attribution

The visible Cloud Billing Reports table, grouped by project, identified project
`902056825143`. The exhaustive `app` grouping for **23–27 October** showed
AccessLife-labelled gross usage **INR693.11**, completely offset by posted
credits, and all unallocated usage **INR1,507.49**, also offset by credits.
Verified unrelated application-labelled usage is excluded. No unrelated
resources were inspected or modified.

Exact allocation of the unlabelled usage is unavailable. Rather than invent it,
this review reserves **all** unallocated gross usage: AccessLife's posted gross
cost is bounded above by **INR2,200.60**, or **US$22.925604** at the previously
verified catalogue ratio INR95.98875/USD. This is an upper bound, not a claim
that the entire unallocated amount belongs to AccessLife. Observed credits are
ignored in the forecast, and no future credits are assumed.

The preceding day matters: the SQL instance was created at 05:06 UTC on
24 October, while billing report days use Pacific time. The earlier 24–27 date
filter missed its first hours. The corrected 23–27 interval covers the recorded
dedicated resource lifetime. Billing can lag more than 24 hours; a separate
US$2 pre-tax allowance covers delayed usage as a forecast reserve, not proof
that the bill is final. Reconcile again before release and stop if the refreshed
forecast exceeds the ceiling.

[Billing day boundaries and reporting delay](https://docs.cloud.google.com/billing/docs/how-to/reports),
[billing latency](https://docs.cloud.google.com/billing/docs/how-to/resolve-issues).

Private, ignored evidence: `.data/tasteduel-cloud-review/billing-reconciliation.json`;
the permitted nonsecret plan input is `approved-cost.json` in the same directory.
The evidence records visible table figures; no billing CSV download is claimed.

## Refreshed cumulative forecast

Forecast interval: **27 October 2026 19:47:28 IST through 7 November 10:15 IST**
(254.458889 hours). Existing SQL, 40GiB growth ceiling and seven backups remain.
Old services/jobs/scheduler/queue were deleted and absence verified before this
forecast; no continuing legacy runtime/model allowance is assumed.

| Component | Pre-tax USD |
|---|---:|
| Posted gross upper bound, including all unallocated usage | 22.925604 |
| Additional billing-latency reserve | 2.00 |
| Existing SQL compute | 20.636616 |
| Full 40GiB SSD ceiling | 2.790840 |
| Seven full 40GiB backup reserve quantities | 9.193354 |
| Bounded web/API compute and requests | 2.01 |
| Vertex envelope | 1.80 |
| Registry/GCS/state | 2.00 |
| Secrets/network/logging/miscellaneous | 3.00 |
| Migration and disposable logical restore allowance | 0.50 |
| **Unrounded subtotal** | **66.856412** |
| **Including 18% tax reserve and 5% FX reserve, rounded upward** | **82.84** |
| **Headroom under approved US$90** | **7.16** |

The original US$62.52 remaining estimate is superseded, not carried forward as
capacity. These are cost forecasts; budget alerts do not enforce spending caps.

## Binding release prerequisites

The smaller runtime allowance assumes at most 25,000 requests, 62,500 vCPU-seconds
and 200,000 GiB-seconds across the window. Vertex assumes at most 50 calls/day,
500,000 input tokens/day and 25,600 output tokens/day across eleven windows.
Shared persisted provider admission controls, caching, generation limits,
request deadlines, min instances zero and bounded scaling must support the
release estimate. Max instances alone does not enforce aggregate spending.
**No public traffic is approved until those limits and a fresh release estimate
are verified.** This foundation contains no Cloud Run product services.

An extended cutover/rollback window, extra paid build, managed-instance restore,
larger traffic/model allocation or unexpected delayed charge requires repricing.
The US$0.50 allowance is not approval for a second managed SQL restore instance.
Exact unlabelled gross attribution remains an accounting limitation, safely
covered here by an explicit upper bound. No exact-attribution completion claim
is made.
