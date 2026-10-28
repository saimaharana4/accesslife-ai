# Candidate cost review — 28 October 2026

**PASS: US$84.03 forecast against the user-approved US$90 cumulative ceiling;
US$5.97 headroom.** This replaces the earlier US$82.84 forecast for candidate
execution. It preserves seven backups and does not authorize public promotion.

Chrome Billing Reports were refreshed at 28 October 00:18:20 IST
(27 October 18:48:20 UTC). The selected 23–28 October interval currently contains
23–27 October Pacific billing days. The exhaustive `app` grouping showed
AccessLife gross INR746.29 and all unallocated gross INR1,602.04. Their sum,
INR2,348.33, is a conservative attribution upper bound, **not** a claim that all
unallocated usage belongs to this application. Separately labelled unrelated
usage is excluded. Posted credits were visible but are ignored; no future
credits are assumed. No billing CSV download is claimed.

The forecast runs from that observation through **7 November 2026 10:15 IST**
(249.944444 hours), covering judging and the reviewed follow-up window. The
catalogue conversion remains INR95.98875/USD. Independent Decimal arithmetic
review reproduced the following figures:

| Component | Pre-tax USD |
|---|---:|
| Posted gross upper bound | 24.464638 |
| Billing latency reserve | 2.00 |
| Existing SQL compute | 20.270494 |
| Full 40GiB SSD ceiling | 2.741326 |
| Seven full 40GiB backup reserve quantities | 9.030251 |
| Bounded web/API requests and compute | 2.01 |
| Vertex envelope | 1.80 |
| Registry/GCS/state | 2.00 |
| Secrets/network/logging/miscellaneous | 3.00 |
| Migration and disposable logical restore | 0.50 |
| **Unrounded subtotal** | **67.81670928845** |
| **18% tax and 5% FX reserves; rounded upward** | **84.03** |
| **Headroom under US$90** | **5.97** |

SQL compute uses US$0.0496/vCPU-hour plus US$0.0084/GiB-hour for 3.75GiB.
SSD and backup reserves use US$0.204 and US$0.096/GiB-month respectively,
with 744 hours. These are the rates from the preceding verified cost review,
not newly discovered discounts. All remaining traffic/model/storage allowances
are retained in full; elapsed time does not reset an allowance.

Binding limits remain 25,000 aggregate runtime requests, 62,500 vCPU-seconds,
200,000 GiB-seconds and the previously reviewed model envelope. This candidate
test is tighter: **at most 12 upstream Qloo requests and six Vertex requests**,
sequential execution, including retries/internal lookups. Persisted daily
admission limits must match those candidate ceilings. No second SQL instance,
extra project, Cloud Build allocation or managed-instance restore is included.
The US$0.50 recovery allowance covers only a short-lived logical database on the
existing dedicated instance and in-memory private export/restore.

Private evidence is ignored under `.data/tasteduel-cloud-review/`:
`release-cost-evidence.json` and refreshed `approved-cost.json`.
Exact unlabelled attribution and final billing remain unavailable; the full
upper bound plus latency reserve is intentional. [Billing reporting delay and
day boundaries](https://docs.cloud.google.com/billing/docs/how-to/reports) remain
limitations. Alerts notify; they do not cap spending. Refresh again before
public release, extra resources, a longer rollback window or changed limits.
