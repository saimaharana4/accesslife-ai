# Taste Duel production cost review

Observed 28 October 2026, **13:08:50 UTC / 18:38:50 IST**. The visible Billing
Reports range is 23–28 October, grouped by `app`. Gross posted usage is
AccessLife **INR853.60**, Taste Duel **INR0.22**, and all unallocated usage
**INR1,737.23**. The conservative accrued upper bound is **INR2,591.05**.
Unrelated labelled usage is excluded; exact unallocated attribution is unknown.
No posted or future credits reduce this forecast. Unposted usage is not assumed
complete: the US$2 billing-latency reserve remains.

**Forecast gate: PASS, US$88.15 of the approved US$90 ceiling; US$1.85 headroom.**
This is a conditional forecast, not a spending cap or settled bill. Refresh and
stop dependent release work if billing, traffic, prices or scope invalidate it.
Keep the seven-backup policy and existing dedicated SQL instance; no second
instance, extra project or managed-instance restore is priced or authorized.

The remaining interval through **7 November 2026 04:45 UTC / 10:15 IST** is
231.6028 hours, rounded upward to **232 hours**. Earlier larger future SQL
estimates are historical; elapsed compute is now included in accrued gross.

| Pre-tax component | US$ |
|---|---:|
| Accrued gross upper bound at INR95.98875/USD | 26.993268 |
| Billing latency | 2.00 |
| Existing SQL: 232h × (0.0496 + 3.75 × 0.0084) | 18.815200 |
| Full 40GiB SSD ceiling, 0.204/GiB-month, 744h | 2.544516 |
| Seven full 40GiB backup reserve quantities, 0.096/GiB-month | 8.381935 |
| Web/API runtime envelope | 2.01 |
| Vertex envelope | 1.80 |
| Registry, GCS and state | 2.00 |
| Secrets, network, logs and miscellaneous | 3.00 |
| Migration and scoped logical restore | 0.50 |
| Public readiness monitoring and maintenance | 3.10 |
| **Subtotal** | **71.144919** |

Apply the unchanged 18% tax and 5% currency reserves and round upward to cents.
The [machine-readable review](../releases/production-cost-2026-10-28.json) is
nonsecret and hash-bound to release operations. Private visible-report and
calculation evidence remain ignored in `.data/tasteduel-cloud-review/`.

Public configuration is bounded to **50 Vertex requests/day**, **500,000
conservatively admitted tokens/day**, maximum 512 output tokens/request;
**100 Qloo upstream requests/day, 12/minute**, including retries/internal lookups;
one maximum instance per service, minimum zero, request-based billing. The
US$1.80 model reserve covers eleven daily windows at 500,000 input tokens and
25,600 output tokens: 11 × (0.5 × 0.25 + 0.0256 × 1.50) = US$1.7974.
[Official model prices](https://cloud.google.com/vertex-ai/generative-ai/pricing).
Promoting existing admission limits must preserve consumed usage, timestamps,
expiry and token rows. No counter reset is authorized.

The runtime reserve assumes at most 25,000 aggregate requests, 62,500 vCPU-seconds
and 200,000 GiB-seconds. These are **forecast assumptions**, not enforced platform
spending limits. Anonymous session creation, denied requests and public static
traffic can still incur charges. Per-session and global provider limits do not
make the Cloud Run bill impossible to exceed. Monitor actual usage; pause
generation/public service access through a reviewed plan before projected spend
crosses the envelope. Budget alerts notify and do not stop billing.

Monitoring explicitly selects three single-location regions (Europe, South
America and Asia Pacific) at **900-second** intervals: at most **3,168 checker
executions** over eleven days, US$0.9504 without a free allotment. Each probe
reaches web and private API, about 6,336 requests inside the runtime forecast.
The larger **US$3.10** reserve is retained for execution, maintenance and logging
contingency. Unspecified checker regions would select all locations and are not
the priced configuration. Dashboard and built-in metrics avoid new custom metric ingestion.
The uptime alert has no external notification recipient; console incidents are
the initial operator surface. [Observability prices](https://cloud.google.com/products/observability/pricing).
Cloud Run jobs bill for at least one minute; reuse the existing one-shot
migration job rather than adding a worker. [Runtime prices](https://cloud.google.com/run/pricing).

The candidate verification allowance is closed at **10 Qloo HTTP requests and
10 Vertex calls**. It does not authorize unlimited public testing. Before a
release-specific live check, record a separate finite ledger, exact tested
configuration, actual counts and stop conditions. No additional provider call
has occurred under this cost review yet.
