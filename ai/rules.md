# AccessLife AI engineering rules

Revision 1 · 24 October 2026 · Applies to all future application, data and infrastructure work

## 1. Authority and current state

Follow explicit user decisions first. The maintained requirements are [prd.md](prd.md), [Architecture.md](Architecture.md), [phases.md](phases.md) and [design.md](design.md). Resolve contradictions before implementing a different product. London, New York, Paris, Berlin and Chicago are required; deployment uses managed GCP services and a separate AccessLife database instance.

Keep the six maintained specifications in `ai/`. Original reference files are preserved locally and ignored; never publish them through a broad `git add .` or use them as runtime dependencies. Record completed work in [memory.md](memory.md), one or two lines per dated entry. Do not mark planning targets as measured outcomes.

Current delivery is documentation and repository setup. Application scaffolding, dependencies, migrations and cloud resources belong to later phases.

## 2. Approved stack and dependency policy

| Layer | Use | Avoid or defer |
|---|---|---|
| Frontend | Next.js App Router, strict TypeScript, React Server Components | Pages Router for new features; making the entire app a client component |
| Styling | Tailwind and semantic CSS variables | Multiple styling systems, scattered status colors and blanket glass panels |
| Primitives | shadcn/ui with React Aria base, Lucide | Mixing primitive bases casually; rebuilding focus/keyboard behavior from scratch |
| Forms | React Hook Form and Zod | Placeholder-only labels; manually duplicating incompatible API schemas |
| Server state | Server Components for initial data; TanStack Query for live browser data | Putting all data in a global client store; storing sensitive plans in shared caches |
| Maps | MapLibre GL JS, optionally its `react-map-gl/maplibre` binding | Assuming free/public tiles permit unlimited use; map-only navigation |
| Charts/motion | Recharts, small custom SVG, Motion | Two chart libraries; mandatory animation; decorative confidence gauges |
| Agent inspector | Lazy `@xyflow/react` | Loading a graph library on every landing page; exposing private reasoning |
| API and DB | FastAPI, Pydantic, SQLAlchemy, Alembic, psycopg, Cloud SQL connector | SQL string interpolation; import-time network calls; schema creation instead of migrations |
| Agents | LangGraph and small explicit provider/tool interfaces | Multiple orchestration frameworks, autonomous unbounded loops or a service per agent |
| Retrieval | MiniLM CPU, pgvector, PostgreSQL full-text search and PostGIS | Chroma/Qdrant/FAISS as additional production stores; GPU; an oversized corpus |
| Generation | Configurable Vertex AI adapter | Local large LLM hosting; guessed model IDs or quota claims |
| Jobs/deploy | Cloud Tasks, Cloud Run jobs, Terraform, GitHub Actions WIF | In-process post-response planning; downloaded CI service-account keys; Kubernetes |
| Verification | pytest, Vitest, Testing Library, Playwright and axe | Skipping failing domain cases, weakening assertions or disabling full accessibility scans |

These are approved implementation choices, not installed dependencies. At scaffolding time select current supported stable Node LTS/Python versions compatible with the chosen stack, pin them in runtime/toolchain files and commit pnpm/uv lockfiles. Use `pnpm` for JS and `uv` for Python. Avoid unpinned `latest` dependencies in repeatable builds and pin container/model revisions.

React Aria base is supported by the [shadcn CLI](https://ui.shadcn.com/docs/cli). Verify generation against the pinned CLI and review copied component code; a registry item is not automatically accessible or safe.

New dependencies need an identifiable missing capability, license compatibility and acceptable browser/image cost. Do not add Redux, Zustand, Storybook, virtualizers, a second UI kit or a full AI chat SDK by default. Add a small local store only when actual shared UI state warrants it. Do not store secrets, profiles or full provider responses in that store persistently.

## 3. Component and contract boundaries

- Domain logic imports ports and pure types, never provider SDKs, FastAPI request objects or frontend concerns.
- Provider adapters normalize raw responses. React cards and validators consume the AccessLife model, not Qloo/GTFS/OSM payloads.
- Configure providers at a composition root; replacing weather or taste must not require editing UI components.
- Python API schemas own the wire contract. Generate TypeScript from exported OpenAPI and check drift in CI.
- Keep business logic in the backend. Next.js API forwarding handles identity, cookies, request/response transport and streaming only.
- Each module owns its writes; expose repository/use-case operations rather than arbitrary cross-module SQL updates.
- Use parameterized SQL, explicit transaction scopes and Alembic migrations. Never hold a transaction open across slow provider calls.
- Preserve immutable plan versions. Replanning uses optimistic concurrency; duplicate/out-of-order requests must not overwrite newer state.
- External network access is injected and mockable. Constructing a module must not start a request, ingest data or mutate infrastructure.

## 4. Evidence and recommendation rules

Hard requirements are gates. A high taste score never overrides inaccessible, unknown, stale or conflicting mandatory facts. “Limited” requires documented compatible conditions and explicit acceptance; do not infer that a caregiver can overcome any limitation.

Store confirmed, limited, inaccessible and unknown as different states. Keep conflict as a separate property. Do not average contradictory facts into a confidence percentage. Track entrance, toilet, lift, boarding, vehicle and walking/rolling links separately.

Every strong factual claim references evidence that actually supports it. Retain provider IDs, URLs, source type, retrieval/update dates, rights and transformation revision. “Fetched today” is not “verified today.” Generic RAG guidance cannot certify operational conditions.

Qloo interest/entity matching must be auditable. Ambiguous candidates stay unmapped; never map solely because a name resembles another venue. Preserve score semantics and scope. Do not invent probabilities, explainability relationships, testimonials or forced ranking changes. Impact comparisons retain the exact same eligible set and snapshot.

Use only explicit user taste interests. Do not infer protected traits or diagnoses from cultural preferences. Never send unnecessary mobility details to Qloo. Do not bulk mirror its graph or responses into RAG without account terms permitting it.

Inter-city travel is user-arranged and unverified in the MVP. Local validation does not establish a fully validated multi-city trip. Straight-line geometry is not a verified accessible route; GTFS is not a routing engine.

Fixtures and development providers are allowed for development and deterministic tests. Label them visibly in the UI. Release qualification requires a live path exercising actual Qloo; changing a label does not convert replay into live evidence.

## 5. Errors, deadlines and partial results

Use typed errors at provider boundaries: invalid input, authentication/permission, rate limit, transient outage, timeout, unsupported capability and malformed data. Map these to a stable safe HTTP envelope. Preserve an internal cause for diagnosis without exposing raw exception text.

| Situation | Required handling |
|---|---|
| Invalid input | Actionable field errors; do not send an avoidable bad request to a provider |
| Authentication/permission failure | Do not retry blindly; report provider unavailable and alert protected operations |
| Timeout/429/temporary 5xx | Retry once only if idempotent and the remaining run deadline permits; honor Retry-After when possible |
| Malformed response | Fail normalization; never fill missing safety fields with optimistic defaults |
| Mandatory evidence failure | Exclude affected candidate/leg from confirmed output |
| Optional source failure | Return explicit partial/provider state; omit unsupported claims |
| Unhandled exception | Safe internal error with request/run correlation; no traceback in browser |
| No eligible result | Explain failed conditions and allow explicit input changes; do not relax requirements automatically |
| User retry | Preserve idempotency keys where retrying the same operation |

Initial ordinary tool deadline is 8 seconds and planning deadline is 30 seconds per attempt. Start at three active local runs, five calls per run and 12 globally. Bound queue attempts and embedding threads; capture cancellation and release resources in `finally`/context-manager paths. Broad exception swallowing, unbounded retry, busy polling, infinite tool loops and silent fallback are prohibited.

Durable tasks must survive client disconnects. Persist graph/run state and ordered events; enforce execution leases and idempotent publication. Reconcile failed enqueue and expired leases. Do not use FastAPI background tasks as the authoritative planning runtime on request-scaled Cloud Run.

SSE reconnects replay durable events after the last sequence; discard duplicates/stale generations. Do not claim completion until plan publication and the terminal event are committed. A cancelled or superseded run must not attach a new trip plan.

## 6. Security, privacy and data admission

- Keep Qloo and model credentials server-side in Secret Manager. `NEXT_PUBLIC_*` is always public.
- Use separate least-privilege service identities. CI uses WIF scoped to the repository and intended environment; no static cloud key files.
- Enforce session ownership for plans, trips, runs and evidence. Opaque IDs alone do not grant access.
- Use Secure/HttpOnly/SameSite cookies, Origin checks for mutations, restricted forwarding paths and parameter validation. Strip untrusted internal headers.
- Rate-limit sessions and expensive actions; cap model calls/tokens and payload sizes. A public anonymous demo still needs abuse controls.
- Never log tokens, mobility profiles, precise user location, raw prompts or provider payloads by default. Log safe request/run IDs, stage, outcome and timings.
- Keep plans/session data `no-store`; do not embed them into public HTML caches, analytics events or URLs.
- Allow users to clear sessions; default active retention is 24 hours. Explain independent backup expiry.
- Allowlist ingestion hosts and types; block loopback/private/link-local/metadata destinations and revalidate DNS/redirect targets to prevent SSRF. Enforce download, decompression, page and parsing limits.
- Treat retrieved content as untrusted data, never instructions. It cannot change tool permissions, system rules or validation gates.
- Use only licensed/authorized sources. Store attribution and rights; do not republish proprietary reviews, guidebooks or unlicensed images.

Ingestion must enforce the Architecture quotas before admitting content: raw 20 GB hard cap, 500 MB clean text, 100,000 active chunks and 2,000 documents. Maintain a ledger and reconcile object versions/staging. Never evict evidence referenced by an active operation merely to make a batch fit.

## 7. UI and accessibility rules

Follow [design.md](design.md). Use visible labels, text plus icons for status, 48 px primary targets, readable contrast and persistent focus indicators. Do not communicate eligibility through color, hover or motion alone.

The list is a complete alternative to the map. Provide buttons for drag/reorder interactions, text/table equivalents for charts and predictable drawer focus restoration. Announce meaningful progress with restrained live regions, not every SSE event or generated token.

Use reduced-motion and reduced-transparency preferences with solid fallbacks. Keep evidence text on opaque surfaces. Never let premium visual effects obscure safety-related facts, unknowns or provider status.

## 8. Verification and release gates

Run meaningful unit/contract tests for validators and provider normalization, transactional tests for versioning/task duplication, retrieval evaluation and browser flows for the main journey. Do not write tests that merely mirror a component's implementation or add needless tests for wording-only edits.

Golden cases cover every city, conflicting/missing facts, excessive distances, unavailable providers, time zones, stale events and cross-session access. Every release claim must point to a measured report, screenshot, test result or live observation appropriate to that claim.

CI should block on lint/type checks, backend tests, schema drift, critical scenarios, build, secrets/dependency checks and full target-page accessibility checks. Separate deterministic fixtures from explicitly invoked live-provider checks. Do not commit provider secrets, full private captures, source documents or model weights to make CI pass.

If a required check fails, fix the implementation or honestly report the blocker. Do not lower thresholds, delete failing cases, fabricate evidence or mark incomplete five-city coverage as done.

## 9. Cloud and change discipline

Use project `project-bb13ecd8-9d67-408d-9a7`, region `asia-south1` unless a verified model capability needs a separate explicit location. Create separate AccessLife resources. Do not modify, restart, delete or share existing PharmaGuard services or its Cloud SQL instance as an undocumented shortcut.

Keep incremental forecast through judging at or below the **US$80 target** before provisioning. Report the actual regional quote and remaining billing/credit uncertainty. Alerts are not hard caps; enforce request, instance, token, storage and log controls. If the design cannot fit, stop provisioning for a concrete budget/design adjustment.

Terraform applies are reviewed against an AccessLife-only inventory; never run broad project destruction. State and credentials remain ignored. Keep migration backups, image rollback references and a tested restore procedure. Default database deletion protection stays on until an intentional teardown.

Retain live access through 5 November and required follow-up. A cleanup checkpoint on 3 November removes only verified unused AccessLife resources. Stopping a service does not prove storage, backups, schedules or image charges have ended.

## 10. Change records

Each completed phase updates its checklist and adds a short `memory.md` entry with actual status. Update PRD, Architecture, phases and design together when behavior changes. README must never present a future feature or deployment as current. Keep secret-bearing transcripts, personal data and original references out of public history.
