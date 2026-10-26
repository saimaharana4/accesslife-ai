# Taste Duel browser integration — Prompt 10

The default shell uses the generated Taste Duel contracts. `/g/[gameId]` and
`/results/[gameId]` render server-owned state through narrow client components.
The original development fixture is available only through `dev:fixtures` and
is omitted from production output. Discovery saves, adaptive solo selection and
fixed friend replay are later iterations; this delivery does not deploy GCP.

## Local entry points

```powershell
corepack pnpm install --frozen-lockfile
uv sync --locked
uv run --no-sync python scripts/tasteduel_local.py migrate
# Unconfigured foundation API, no external calls:
uv run --no-sync python scripts/tasteduel_local.py api
# Default shell in another terminal; this uses the bounded live API on 8004:
corepack pnpm dev:live
# http://127.0.0.1:3001
```

The foundation API uses port 8002. To point the shell at that service for
non-provider debugging, configure `TASTEDUEL_API_URL=http://127.0.0.1:8002`
when invoking Next directly, with the exact local origin and local HTTP flag.
`dev:live` intentionally uses a separate port 8004 for the explicitly bounded
live harness; it cannot silently turn the default foundation API live.

`scripts/tasteduel_web_live.py --serve` uses the existing Secret Manager
reference through SDK ADC in memory, the explicit `http_ranked`/typed-search
escape hatch and the pinned Vertex model. It requires a pre-reviewed, existing
ignored `.data/tasteduel-prompt10/live-budget.json`. The Prompt 10 ceiling is
eight upstream Qloo dispatch reservations and six Vertex HTTP requests, including
retries/internal lookups, enforced before dispatch. The ledger is never reset
on resume and must not be renewed to work around a failure. An exclusive local
lock permits one owner. The normal per-generation six-Qloo/four-Vertex/20-second
limits and shared SQL provider admission remain active. Cold credential refresh
is separate from that game deadline. The retained ledger may be closed after
verification: do not reopen it simply to replay this test.

`node scripts/tasteduel_browser_live.mjs --run-live` is an explicit real-provider
check, never a default test. It uses one game for all three viewport captures,
checks public responses only in memory, stores no cookies/traces/provider
payloads, and proves answer/Next add no upstream calls. Screenshots and minimal
audit summaries belong in ignored `.data/tasteduel-prompt10/`.

For deterministic checks without credentials:

```powershell
corepack pnpm test:web-contracts
corepack pnpm typecheck
# Start default nonfixture Next on 3001, then run fully intercepted synthetic APIs:
corepack pnpm test:web-integration
corepack pnpm build
corepack pnpm check:fixture-production
# Production-output loopback preview against the metered API:
corepack pnpm start:live
```

The Playwright integration suite replaces every browser API request with
explicitly synthetic contracts; its passing results are not live-provider proof.
Ctrl+C stops each preview/API. Database stop retains data:
`uv run --no-sync python scripts/tasteduel_local.py stop`.

## Browser/private API boundary

- Fixed configured private origin; explicit method/path/query allowlists.
  No client-selected host, URL, Authorization or forwarded identity is trusted.
- Exact origin validation for mutations. HTTPS required except an explicit
  loopback development setting. Forward only the own guest cookie and required
  idempotency key; reconstruct host-scoped HttpOnly SameSite=Lax cookies with
  Secure on HTTPS. Never forward upstream diagnostic headers.
- Server-only optional Cloud Run IAM identity comes from the fixed metadata
  endpoint, with the configured private API origin as audience. This is locally
  synthetic-tested, not proof of deployed IAM connectivity.
- Validate request and response bodies against the application's exported
  OpenAPI, including nested allowlists. Bound actual streamed bytes, timeouts and
  redirects. Known public errors use fixed copy; unknown diagnostics are not echoed.
- Search aborts stale queries and preserves explicit identity selection. No
  guessed artist/movie identity is silently accepted.
- Only the current playable DTO reaches the browser. An accepted reveal may
  show its winner and factual frozen-context sentence. Richer explanation text
  remains withheld. Global curation summaries appear only after five answers;
  the full receipt, private pools, scores and future choices stay server-private.
- Generation and mutation intents persist only minimal user input/key in
  optional sessionStorage. Uncertain retries retain the same body/key; GET can
  settle an accepted action. No session credential is stored by JavaScript.

## Artwork and disclosure

Only exact project-owned asset IDs/local SVG paths render. Provider image
metadata does not establish permission and is never fetched. There is no remote
image proxy, redirect-following image fetch or arbitrary URL input. Native local
art preserves readable titles outside the image, intrinsic dimensions and
image-failure fallback. The Next image optimizer has no remote allowlist, and
the browser CSP permits only local/data imagery.

Every live game names Qloo as ranking source and identifies actual agent versus
deterministic mode. The post-answer “Why this duel?” disclosure states the
accepted ranking context without inventing psychology or causation. Optional
“Curated with Qloo” uses only the completion summary and remains secondary to
the game. Fixture provenance remains explicit wherever synthetic results occur.

## Verification and release limits

### Verification on 26 October 2026

- 52 Node forwarding/client/intent/gameplay checks passed; TypeScript and actual
  exported-OpenAPI drift passed.
- 23 distinct Playwright project cases passed (28 passing invocations including
  targeted reruns). There were 38 successful full axe scans/captures, without
  exclusions. Core journeys run across desktop/390/320; additional generation
  claim and delayed-navigation recovery cases were checked on desktop. Latest
  search and desktop journey captures supersede their earlier copies.
- Production build and fixture exclusion across 268 emitted files passed. A real
  standalone origin mismatch was fixed by selecting only a unique configured
  origin matching the raw Host; forwarded host/protocol headers remain ignored.
- One genuine production-output browser game completed Radiohead artist → five
  movie comparisons → server score, labelled agent curated. Exactly two Qloo
  HTTP dispatches (search and ranking) and two successful Vertex HTTP requests
  occurred. Five answer and five Next mutations added none. Twelve live captures
  cover seed/unanswered/reveal/result at all three widths, with no overflow.
- Inspected actual live renders and synthetic open-search, expanded curation,
  long-title, failed-SVG, expired and provider-error renders. Browser-network checks
  found no key/private pool/raw affinity or unanswered winner fields; no external
  image/browser destination was requested. This is bounded inspection, not a
  claim of complete abuse resistance or a human assistive-technology audit.

Artifacts: ignored `.data/tasteduel-prompt10/{verification,browser-summary,
live-budget,independent-browser-review}.json`, twelve live PNGs and
`test-results/tasteduel-integration{,-artwork,-search,-generation,-navigation}/`. The live API
retains its non-renewing remaining allowance for the local preview. Prior ledgers
remain closed/exhausted. Ctrl+C stops the preview/API; an interrupted owner can
leave a lock that requires checking no API process remains before removing that
empty lock, without resetting the ledger.

Final navigation regression: an accepted creation response arriving after leaving
the page cannot redirect it. Unmount aborts the browser request and leaves the
minimal intent available; Back plus explicit recovery uses the identical key/body.
Only affected synthetic creation/keyboard checks were rerun after this fix;
provider code and visual composition remained unchanged, so the live check was
not repeated and the upstream counts stayed two/two.

### Unresolved release gates

Prompt 8's stronger live feedback-driven corrective-value gate is still open
unless a separate actual execution establishes it; a five-round live browser
pass does not establish adaptive value, broad artist/movie coverage or human
surprise. Canonical MCP typed resolution remains unverified; the explicit tested
HTTP transport is documented rather than hidden. Legacy runtimes bypassing
shared key admission need coordination before rollout. No production identity,
cloud database, IAM deployment, share link or external launch is changed here.
