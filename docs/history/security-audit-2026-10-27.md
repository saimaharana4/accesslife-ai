# audit — 27 October 2026

> Historical validation record. Statements below describe the dated checkpoint, not current deployment status. See the [current documentation](../README.md).

Local hardening and production-build lab evidence. No deployment, cloud changes,
provider calls, credential payload access or fresh live-integration claim.

## Findings fixed

- Replaced unrestricted production inline scripts with fresh 32-byte CSP nonces,
  `strict-dynamic`, no script attributes, no framing/objects/base URL and local
  image/font/network destinations. Proxy overwrites caller CSP/nonce headers.
  Request-time rendering prevents static nonce reuse. React Aria inline styles
  remain an explicit compatibility allowance; production has no `unsafe-eval`.
- Kept the guest control footprint stable before session retrieval. Mobile header
  growth of 66 px caused the original landing CLS of 0.1438; it is now 0.04969.
- Guest disclosure closes on Escape, outside focus and clearing. Focus returns to
  the summary or wordmark as appropriate; the next link is no longer occluded.
- Async game/result/invitation fallback states now announce politely. Accepted
  reveal focus/announcement stays separate and is not duplicated.
- Fixture provenance takes precedence over any contradictory curator-mode flag.
  Fixtures cannot claim genuine agent execution in the curation disclosure.
- Added bounded guest/provider admission, request-body deadlines/chunk limits and
  exception containment that prevents raw failure messages entering ASGI logs.
  Local startup disables access logs so search URLs are not recorded there.
- Session clearing bypasses admission limits while retaining origin and session
  checks, so throttling cannot prevent revocation. Regression checks cover lost
  clear responses, stale-cookie renewal and anonymous invitation access with an
  unrelated expired/revoked cookie. Expired fixtures insert separate identities;
  no immutable session timestamps or database protections were changed.

## Abuse and secrecy boundary

Immutable additive `td0009` stores private hash-scoped counters under RLS. All
instances using the same store reserve atomically before external work; failures
consume admission too. Guest identity is a verified random session, never an IP
or forwarded-header assertion. Settings allow finite, bounded overrides.

| Default envelope | Limit |
| --- | --- |
| Guest reads | 240/minute |
| Guest mutations | 120/minute |
| Guest search | 12/minute |
| Guest generation | 6/10 minutes |
| Shared Qloo | 30/minute and 1,000/day per key fingerprint |
| Shared Vertex | 100 requests and 1,000,000 conservative tokens/day per project/model |
| Mutation body | 16 KiB, 256 chunks, five seconds; web forwarding remains 8 KiB |

Daily counters use UTC-aligned windows; the lower configured limit wins within a
window. Vertex reserves a conservative UTF-8 input bound plus maximum output,
including bounded continuation signatures, before SDK transport. This is an
engineering envelope, not an invoice or a guarantee of Qloo event quota. Existing
per-generation deadlines/requests, circuit/auth blocking and cache/evidence expiry
still apply. Database failure denies provider admission rather than bypassing it.
Typed 429/408 envelopes survive the strict web forwarding boundary.

Cookie cycling and anonymous invitation/new-session traffic remain possible.
Provider ceilings constrain paid upstream usage rather than proving bot resistance.
An independently running legacy service that bypasses this store is **outside**
the shared ceilings: reconcile/disable it before deployment. Inactive hashed
counter scopes still need operational deletion; expired windows become ineffective
and are replaced on reuse. Physical evidence purge and backup reconciliation also
remain release obligations. Do not claim one IP throttle protects all users.

Before acceptance, public DTOs contain no answer/rank/affinity, future contestant,
unused pool or private receipt. Curation summaries remain withheld until all five
answers; accepted-round Why-this-duel evidence is separately authorized. Genuine
agent, deterministic Qloo and synthetic fixture modes use explicit text. Model
thought text, raw Qloo responses and credentials are not public projections.

Evidence combines independent source review, backend contract/caplog checks,
browser DOM/network checks and actual production BFF HTML/RSC/invitation/DTO/OG
checks with malicious synthetic metadata. The rendered title is escaped, future
canaries stay absent, and source selection is not converted to a preference.
`tasteduel_prompt13_exposure.py` separately scanned 15 emitted public JS assets for
credential patterns, private-contract canaries and server provider destinations:
zero findings. That pattern scan alone is not an exhaustive secrecy proof.

## Accessibility and visual evidence

The recorded full browser baseline has 33 passing cases across 1440×1000,
390×844 and 320 px. It covers complete keyboard solo/fixed journeys, combobox,
reveal/result, Why-this-duel/curation, truthful modes, interrupted/expired states,
image failure, long titles, reduced motion and focus restoration. No axe rules
were excluded. The final affected rerun additionally covers expired results,
polite fallback announcements and guest-panel Escape/focus occlusion.

Passed 665 backend tests and 61 Node contract/state/CSP checks. The browser audit
passed 36 distinct cases: 33 baseline cases plus 21 affected reruns/new checks,
with 117 full axe executions and zero violations. Baseline: 66 complete axe
scans, zero violations; 1,368 computed colour samples.
Minimum sampled opaque enabled-text contrast was 8.29:1. Disabled Start text was
4.10:1, recorded as disabled-control contrast rather than hidden by an exclusion.
Loaded local fonts, actual renders and 48 px primary/disclosure targets were
checked. Final counts are recorded in `.data/tasteduel-audit/verification.json`.

**Manual boundary:** visual inspection and agent-driven keyboard browser checks
are not human usability or screen-reader testing. The 200% test uses CSS zoom
emulation. Actual browser-UI zoom could not be operated: the computer-use helper
twice returned `Computer Use native pipe is unavailable` (Windows error 2).
Actual native zoom and assistive-technology acceptance remain unverified. An axe
pass does not establish screen-reader support. These are explicit release checks.

## Measured production performance

Full lab build `p5YUsz9Uw8PsNfspumuMJ`: 16 navigations (five fresh-cache and three
warm-cache per route), five pressed-feedback samples and 30 accepted warm answers
after five excluded warm-ups. The final focus-handler-only build
`1kfCYmki-5LIXRx3Jg_MO` has a separate two-navigation/one-press smoke and fresh JS
byte measurement. Prior full measurements are linked, not presented as new
samples or pooled into a larger sample count.

| Metric | Measured | Target |
| --- | --- | --- |
| Final landing/game LCP, one cold-cache sample each | 1.416 / 1.064 s | ≤2.5 s |
| Final landing/game CLS | 0.04969 / 0.03103 | ≤0.1 |
| Initial JS, actual requested bodies gzipped | 144,636 bytes | about ≤180,000 |
| Additional gameplay JS | 8,328 bytes | ≤100,000 |
| Pressed DOM commit, full n=5 / final n=1 | 19.4–41.6 / 76 ms | <100 ms |
| Warm answer p95, nearest rank, n=30 | 132.71 ms | ≤500 ms |

Full cold landing LCP was 1.072–1.264 s; cold gameplay 1.064–1.252 s. Warm ranges
and every raw sample remain in the private report. Answer median was 120.37 ms,
maximum 137.09 ms; no duplicate-answer fast paths were used as accepted samples.

Windows, Ryzen 5 5500U, Node 24, Chromium 156, 390×844, reduced motion; CDP 4× CPU,
150 ms RTT, 1.6 Mbps down/750 kbps up. “Cold” means fresh browser context/cache,
**not cold server**. API timings include loopback HTTP and real PostgreSQL, but
exclude BFF, TLS, cloud cold starts and production-scale data. Press timing is
programmatic click to committed `aria-pressed`, with answer transport held; it is
not hardware latency or field INP. Gzip totals may differ from server encoding.
No maps, graphs, embedding/model assets or animation library are loaded. Every
measured target passed; zero CSP violations/external browser/provider requests
were observed in the lab. No field INP/p75 or Lighthouse population claim is made.

## Dependency review and remaining release gates

Registry snapshots returned zero known advisories: pnpm audit (149 reported
dependencies), root Python runtime lock (78 packages) and isolated Taste Duel
runtime lock (48 packages). There was no advisory requiring a severity/reachability
fix in those snapshots. The isolated image excludes legacy planner/RAG libraries;
the wider development environment does not. These checks do not audit OS images,
future advisories or prove zero risk. Keep lockfiles and repeat at the packaging
stage if dependencies/images change.

No unresolved serious/critical defect was identified within the executed checks.
This is **not production release clearance**: manual AT/native zoom, external
crawlers, deployed IAM/headers, legacy key coordination, retention cleanup and
the earlier live corrective-agent-value gate remain open. Next: Prompt 14.

## Reproduce

Use [local startup](CHALLENGES.md) with provider-disabled API8005 and web origin
3001 (or the configured dev origin3003). Full browser/performance scripts require
the production standalone build served on 3001 with API8005 and explicit local
canonical origin; they never reset the recognized local database.

```powershell
uv run --no-sync python scripts/tasteduel_local.py migrate
corepack pnpm contracts
corepack pnpm build
# Terminal 1:
$env:TASTEDUEL_ALLOWED_ORIGINS='["http://127.0.0.1:3001"]'
$env:TASTEDUEL_QLOO_ENABLED='false'
$env:TASTEDUEL_GENERATION_ENABLED='false'
uv run --no-sync python scripts/tasteduel_local.py api --api-port 8005
# Terminal 2:
$env:TASTEDUEL_API_URL='http://127.0.0.1:8005'
$env:TASTEDUEL_WEB_ORIGINS='http://127.0.0.1:3001'
$env:TASTEDUEL_CANONICAL_ORIGIN='http://127.0.0.1:3001'
$env:TASTEDUEL_ALLOW_LOCAL_HTTP='true'
$env:TASTEDUEL_API_IAM='false'
node scripts/start-prototype.mjs
# Terminal 3, while those servers run (http://127.0.0.1:3001):
corepack pnpm test:web-contracts
corepack pnpm test:audit
uv run --no-sync python scripts/tasteduel_local.py test -q
uv run --no-sync python scripts/tasteduel_audit_performance.py
uv run --no-sync python scripts/tasteduel_audit_performance.py --quick
uv run --no-sync python scripts/tasteduel_audit_surfaces.py
uv run --no-sync python scripts/tasteduel_audit_exposure.py
corepack pnpm check:fixture-production
```

Stop the owned standalone server before rebuilding on Windows to avoid file locks.
Run the performance lab with other browser suites paused. Build/artefact commands
do not provision cloud resources. Private reports/screenshots are ignored under
`.data/tasteduel-audit/` and `test-results/tasteduel-audit/`.
