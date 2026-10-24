# AccessLife incremental cost gate — 24 October 2026

Window: 24 October through 5 November (13 days / 312 hours). Target **US$80**, excluding unrelated existing workloads. This review authorizes only the AccessLife resources in this repository. Recalculate before extending the window or increasing limits.

| Item | Conservative allowance | Basis |
|---|---:|---|
| Separate Cloud SQL Enterprise PostgreSQL 16, Mumbai | $25.31 | 1 vCPU at $0.0496/hour plus 3.75 GiB at $0.0084/GiB-hour, 312 hours |
| SQL SSD, backups and bounded growth | $4 | Initially 20 GiB; maximum automatic growth 40 GiB, seven retained backups |
| Cloud Run services and maintenance jobs | $12 | Scale to zero, web/API max two instances, worker max one; three planning executions, 30-second execution deadline; bounded demo traffic |
| Vertex generation | $18.20 | Reserve at deliberately conservative $5/M input and $25/M output; 35 calls/day, a 2,000-input-token planning allowance and 1,200-output-token cap/call over 13 days |
| Builds, registry and private buckets | $2 | Local builds pushed to registry; small images/corpus; no GPU/VM/VPC connector |
| Network, Secret Manager, Tasks and monitoring | $5 | Small demo traffic and few secrets, no free-tier credits assumed |
| Usage subtotal | $66.51 | Before tax |
| Conservative 18% GST reserve | $11.97 | Account currency is INR; do not assume a tax exemption |
| **Forecast allowance** | **$78.48** | **Passes the $80 gate including the tax reserve** |

Cloud SQL regional rates were retrieved directly from the authenticated Google Cloud Billing Catalogue API: service `9662-B51E-5089`, Mumbai PostgreSQL zonal vCPU SKU `DF80-E0D1-CCE3`, RAM SKU `72C1-62A1-2C8B`. Existing PharmaGuard resources were inspected read-only and are excluded.

Sources: [Cloud SQL pricing](https://cloud.google.com/sql/pricing), [Cloud Run pricing](https://cloud.google.com/run/pricing), [Vertex generation pricing](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing), [Secret Manager pricing](https://cloud.google.com/secret-manager/pricing).

The model allowance is an upper planning rate, not a quoted model tariff. Generation input is bounded by validated inputs and a small deterministic prompt; output is capped in the SDK. SQL continues billing while idle. An indefinite monthly rollout needs a new review. Cloud Run instance limits, quotas and alerts do **not** impose a dollar spending cap. Traffic exceeding the assumed demo load requires review and may require taking the public service offline. The app limits model calls independently of browser sessions.

Budget alerts use `app=accesslife`, an INR usage-subtotal threshold equivalent to US$80 / 1.18, and 50/75/90 percent thresholds through 6 November; services that do not propagate this billing label require separate review in Billing Reports. Alert coverage is not complete spend accounting. Check AccessLife costs daily, including unlabelled generation and networking.

Teardown after judging requires an explicit decision: retain an encrypted backup, disable scheduled jobs and traffic, remove runtime resources, then separately remove SQL deletion protection before destroying that instance. Do not tear down unrelated project resources. Do not destroy data or disable the Qloo secret as part of routine application shutdown.

The billing account reports INR, so a USD-denominated budget was correctly rejected by Google. Use the current INR/USD ratio from the same Mumbai CPU SKU to convert the alert subtotal. Catalogue prices exclude tax. An 18% reserve is included without assuming a particular GSTIN/contract status; see [Google's India tax rules](https://docs.cloud.google.com/billing/docs/resources/vat-overview#india). The earlier US$74.31 usage-only estimate is superseded by this tax-inclusive review and the smaller cloud generation allowance.

24 October catalogue conversion: the same CPU SKU is INR 4.761041999/hour versus USD 0.0496/hour, giving a catalogue ratio of INR 95.98875 per USD. The alert's usage subtotal is conservatively floored to **INR 6,507** (`80 / 1.18 * 95.98875`). With the 18% reserve, this stays within the US$80 envelope at that catalogue ratio. This is a tariff conversion for the review date, not a guaranteed future foreign-exchange rate.
