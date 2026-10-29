# Named challenges release cost refresh

Observed 29 October 2026, 14:53 UTC. No production changes have been made
under this refresh. **Gate: PASS against the explicitly approved US$100 ceiling.**

Google Cloud Billing Reports, charge period October 23–29, grouped by `app`,
shows gross usage of INR1,112.91 for AccessLife, INR1.05 for Taste Duel,
INR2,069.11 unallocated, and INR1,079.18 for the unrelated PharmaGuard label.
Using the previous conservative attribution rule, the accrued upper bound is
INR3,183.07. The unrelated labelled amount is excluded. Credits do not reduce
this forecast; zero payable is not zero usage. The initial whole-month view
was INR6,883.73 and is not the comparable release-period figure.

At the previous review conversion of INR95.98875/USD, with 206 remaining hours
rounded upward through November 7, 04:45 UTC, the forecast is:

| Pre-tax component | US$ |
|---|---:|
| Accrued gross upper bound | 33.160865 |
| Billing latency reserve | 2.000000 |
| Existing SQL, 206h × (0.0496 + 3.75 × 0.0084) | 16.706600 |
| Full 40GiB SSD ceiling, 0.204/GiB-month, 744h | 2.259355 |
| Seven full 40GiB backup reserve quantities, 0.096/GiB-month | 7.442581 |
| Existing web/API envelope | 2.010000 |
| Existing Vertex envelope | 1.800000 |
| Registry, GCS and state | 2.000000 |
| Secrets, network, logs and miscellaneous | 3.000000 |
| Migration and scoped logical restore | 0.500000 |
| Existing monitoring and maintenance | 3.100000 |
| Additional cleanup, polling and alert reserve | 3.000000 |
| **Subtotal** | **76.979401** |

With the unchanged 18% tax and 5% currency reserves, rounded upward:
**US$95.38**. This exceeded the former limit by US$5.38. The user explicitly
approved “Approve $100 ceiling and deploy” on October 29, 2026. The updated
ceiling leaves US$4.62 forecast headroom. The hash-bound machine-readable
review records this approval; historical reviews retain their US$90 default.
Existing billing alert thresholds remain conservative early warnings, not
spending caps or the current approved ceiling.

The new reserve assumes six cleanup launches/hour, normally one billed minute
at 1 vCPU/512MiB, plus retries, bounded polling and low-volume log metrics.
Google bills Cloud Run jobs for at least one minute; Scheduler charges per job,
including paused jobs, rather than per execution. Neither free-tier allowance
nor trial credit is assumed. These are forecast assumptions, not a hard
platform spending cap. A sustained timeout/retry storm requires operator action
and a refreshed forecast. Preserve the seven-backup policy, current SQL instance,
provider counters and one-instance service limits.

Sources: [Cloud Run pricing](https://cloud.google.com/run/pricing),
[Cloud Scheduler pricing](https://cloud.google.com/scheduler/pricing),
and the [previous cost methodology](production-cost-review-2026-10-28.md).

The cost approval does not replace exact-source CI, independent saved-plan
review, migration checks or controlled traffic promotion.
