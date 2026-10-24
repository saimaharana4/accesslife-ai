# Taste Duel engineering rules

Revision 3 — 24 October 2026 — Prompt 1 specification reset. **These rules describe the Taste Duel target. Existing code/runtime remains AccessLife AI.** Rewriting specifications does not complete game development, provider verification or a GCP migration.

## 1. Authority, scope and preservation

Follow the user's explicit Taste Duel pivot, [prompts.md](prompts.md) and the maintained [PRD](prd.md), [Architecture](Architecture.md), [phases](phases.md) and [design](design.md). Execute only the selected numbered prompt. Complete its checks or report the specific blocker; do not skip into later implementation/deployment. Routine reversible decisions do not require repeated approval. Prompt 1 authorizes documentation/preservation, not cloud mutations or application replacement.

Build a guest web game: seed search, five Qloo-backed comparisons, honest score, discoveries and exact friend challenge. Initial artist/movie coverage is a live gate; book/person support is later. Remove the old five-city/planner requirement. Native apps, accounts, global leaderboards, maps, transport, multi-city travel and extra domains are outside this MVP.

Use available Codex agents with explicit independent file ownership, coordinated contracts and an independent reviewer. Those build roles are not deployed agents. The application starts with one bounded RoundCuratorAgent; extra frameworks/agents/services are not evidence of quality.

Preserve original `/ai` reference bytes and a recoverable AccessLife source checkpoint/history. Publish only specifically allowlisted AI documents: the six maintained specs, ai/prompts.md and the dated [Qloo capability matrix](qloo-capability-matrix.md); originals remain local/ignored. Never broad-stage credential history, private captures, state or original references. Keep dated short factual [memory.md](memory.md) entries and mark historical AccessLife evidence clearly. Do not edit external user memory without a direct request.

## 2. Approved stack and dependencies

| Layer | Use | Avoid or defer |
|---|---|---|
| Web | Next.js App Router, strict TypeScript, Server Components for shell/layout | Whole-app client rendering, old planner reskin, new Pages Router flow |
| Style/controls | Tailwind, semantic tokens, React Aria primitives, Lucide where useful | Mixed UI bases, copied trade dress, improvised focus/combobox behavior |
| Interaction | Motion for focused choice/reveal; explicit frontend state machine | Forced animation/audio, GSAP/WebGL without a measured need |
| Contracts | Generated application OpenAPI types and compatible Zod forms | Conflicting handwritten wire schemas, private payloads in public global stores |
| API | FastAPI, Pydantic, SQLAlchemy, Alembic, psycopg | SQL interpolation, import-time requests, create_all instead of migrations |
| Qloo | Pinned official harness/Python stdio MCP client behind QlooPort | Browser keys/calls, docs MCP as production API, guessed tool arguments |
| Agent/model | One Google Gen AI Vertex tool loop and typed model port | Inherited RAG supervisor/swarm, unbounded loops, guessed model IDs |
| Storage | PostgreSQL 16 ordinary relational tables | RAG/PDF ingestion/chunking/embeddings/MiniLM/vector/spatial requirements, Redis by default |
| Runtime/release | Node 24, Python 3.12, Docker, Terraform, GitHub Actions WIF | Runtime npx installs, unpinned latest, Kubernetes, CI service-account key files |
| Checks | pytest, meaningful frontend checks, real DB integration, Playwright/axe | Weakened assertions/scans, fixture success presented as live evidence |

Use pnpm/uv, compatible exact dependencies/images and committed lockfiles. Verify harness/runtime versions in Prompt 2; the Python backend image also needs the tested Node runtime. Do not retain unused retrieval/map/chart packages because they already exist. Remove dependencies only after replacement stages pass and imports/build/runtime checks establish they are unused. Reused SQL extensions can remain installed harmlessly.

Every new dependency needs a missing capability, compatible licence and acceptable browser/image/maintenance cost. No second orchestration framework/model provider/cache/chart kit/account system by default. Optional old generation providers remain disabled unless deliberately configured with rotated credentials; the target uses Vertex IAM.

## 3. Modules and contracts

- Fresh backend domain: apps/api/src/tasteduel. Frontend features: seed, duel, reveal, results, challenges, discoveries. Do not simply rename old planner modules.
- API/UI call application use cases; domain imports pure types/ports, not FastAPI/provider SDKs/raw Qloo JSON/React. Wire adapters at a composition root.
- Pydantic application schemas own HTTP contracts. Generate web types from actual exported application OpenAPI and check drift. An advertised generic OpenAPI meta-schema without paths is not a Qloo endpoint spec.
- Keep distinct unanswered and accepted-reveal DTOs. Private snapshots/pools/persistence objects never serialize directly to browsers.
- Deterministic backend rules own game decisions. Next.js forwarding handles safe transport/identity, not trusted scoring.
- Parameterize SQL, use short transactions/constraints/expected revisions and never hold a connection across provider/model IO.
- Inject network, clock and RNG for meaningful tests. Importing/constructing a module must not call providers, migrate data or mutate cloud.

## 4. Qloo semantics, sources and retention

Resolve typed IDs and ask users to settle material ambiguity. Search results are candidates, not proof of identity. Allowlist verified types/parameters; unsupported parameters may not fail helpfully. Actual workflows/arguments come from discovered pinned harness schemas. Application tools such as evaluate_pool are not official Qloo agents.

Contestants in each duel share a target type and frozen context: seed/signals, filters, provider/harness version and snapshot. Never compare raw scores across domains, changed requests/filters or demographic contexts. Cross-domain means seed and target actually differ, not two artists for an artist seed.

Verify wire score units/order before normalization/display. Prefer rank wording. No invented enjoyment probabilities, causal explanations, psychological labels or claims that scores measure a player's cultural worth. Qloo supplies the answer for that query, not universal cultural truth. Preserve ambiguous/missing metadata rather than inventing a plausible match.

Prompt 2 observed decimal `query.affinity` in two explicitly affinity-sorted raw responses; this does not establish universal units or canonical MCP default ordering. Reject conflicting score fields; preserve `types[]`/subtype and matching interpretation context during normalization. Top-level warning absence does not prove absence of nested explainability warnings. The [capability matrix](qloo-capability-matrix.md) lists unresolved probes; do not reset its consumed 12-request budget. HTTP cache `Expires` is not credential expiry.

Reject same/self pairs, wrong types, repeated contestants, ambiguous identity, unverifiable order, contradictory metadata, ties/near-ties and missing/nonfinite required scores. Arbitrary ID/name tie-breaks do not establish factual winners. Difficulty bands are versioned game heuristics calibrated from outputs/player observations, not universal attachment deltas or statistical confidence.

Send only the selected public cultural seed and permitted context to Qloo. Do not send names/emails/session IDs/location histories or infer sensitive traits. Optional TMDB/Wikidata/Commons metadata cannot become an alternate ranking engine. Cache only project-needed data privately with scope, rights, timestamps, version and expiry; no bulk graph mirror or artificial RAG corpus. Live response captures stay private/ignored, never Git or public endpoints.

Review applicable event/API terms for raw data, evidence, metadata, assets, games/challenges, logs and backups. Do not invent a fixed TTL as a licence condition. Conservative product defaults apply only where terms permit. Challenge expiry is no later than evidence expiry; expire/revoke rather than silently re-querying its answers. Session clear revokes owned live access/shares under the documented policy; backup expiry is separate, not instantaneous erasure.

An image URL is not permission to mirror/transform/use artwork in social cards. Record per-asset source/licence/attribution/uses. Approved images or original title-based SVG/CSS fallbacks are allowed; broken images and fake posters for real works are not. Do not scrape Google Images/Letterboxd, assume Commons media is CC0 or add Spotify OAuth for covers. TMDB terms/credential/attribution and linked-media rights require their own review.

## 5. Agent authority, game rules and answer secrecy

RoundCurator chooses verified domains, calls allowlisted tools, inspects validation and makes a bounded correction. CandidateValidator owns eligibility, frozen Qloo order supplies winners, GameEngine owns delivery/scoring/adaptation, ChallengeService owns replay. The model cannot create entities/scores or override a veto. Precompute supported reveal text or use a factual template; correlation does not support invented personal/causal stories.

Validate initial limits: around 20 seconds total, at most six upstream Qloo calls including retries/internal harness lookups, normally two and at most four Vertex requests, finite tokens/tool steps and repetition/cancellation checks. Coordinate per-key budgets across instances and overlapping legacy readers. Count actual upstream calls or conservative verified workflow maxima; one MCP invocation is not necessarily one HTTP call. Exhaustion is a useful failure state, not permission for an extended loop.

Before acceptance, winners/ranks/affinities/revealing copy/remaining pools/answer-dependent URLs must stay out of JSON, HTML, RSC/preload/prefetch, bundles, accessible labels, public logs, analytics and OG images. Choice order cannot simply preserve upstream ranking. Persist independently assigned sides and opaque IDs.

After acceptance, only that round may reveal its winner/evidence and real score. Separate accepted DTOs allow resume of saved current feedback and completed results may show answered rounds; neither grants future-answer disclosure. Audit every read transport, not just answer submission.

Exactly five accepted rounds, distinct contestants, one point per correct prediction and maximum five. Prove no-repeat continuation before selecting an adaptive pair; scarce-band fallback remains explicit. Do not silently relax quality to fill slots. Never trust browser totals, use speed multipliers or display fake percentiles/testimonials/live counts.

Freeze the creator's actual five played rounds, order/sides/question contexts/answers/scoring and validator versions. Friend replay is guest-owned and fixed, never independently adaptive. Answer, explicit Next and replay cause no Qloo/Vertex calls. Compare only inside the same challenge definition. This is casual play, not cheat-proof competition; external research and repeated plays exist.

Label deterministic Qloo-backed curation when Vertex fails and synthetic fixtures during development. Neither proves live agent use. A model narrating a fixed pipeline is not autonomous tool reasoning. Mocks/replays alone or changed labels do not satisfy the live integration gate.

## 6. Request ownership, errors and recovery

Persist session/operation idempotency key, canonical body hash, stable game ID, bounded lease/fence and usage/attempt counters. Await generation within its active HTTP request and publish the pool/first round atomically before ready. Changed bodies conflict; lost-response retry recovers the same game. Stale claims cannot publish after replacement, revocation or evidence expiry.

202 may describe an already-running claim with observation/retry guidance, not an undeployed queue's promise. Handler loss leaves a reservation explicitly reclaimable after expiry under bounded attempts. Do not rely on FastAPI BackgroundTasks, unobserved promises/RAM or post-response Cloud Run work. If measured generation needs durable dispatch, design/test that change before adding it; do not silently activate the old worker.

Answer/advance use transactions, unique acceptance and expected revisions. Identical retries return saved outcomes; conflicting choices/bodies return 409. Future/out-of-order IDs fail. Session clear blocks late publication. Expired games do not silently become new games. Release permits/resources on cancellation/failure.

| Condition | Required handling |
|---|---|
| Invalid/ambiguous input | Actionable validation/selection, no guessed identity |
| Qloo auth/permission failure | No blind retry, silent transport/provider switch or fixture success |
| Timeout/eligible 429/temporary 5xx | Bounded idempotent retry within deadline/quota; Retry-After where feasible |
| Partial/degraded harness result | Explicit normalized status; normal deterministic quality gates still apply |
| Malformed order or weak pool | Reject unsupported pairs and offer another seed |
| Vertex unavailable/refusal/malformed output | Label deterministic curation/template fallback only where real Qloo permits |
| Artwork failure | Preserve title and deliberate owned fallback |
| Internal/database error | Stable safe envelope/correlation ID; no traceback/query/payload |
| Lost answer/advance response | Saved outcome/round; no duplicate score or reshuffle |

Normalize ok, empty, needs_input, partial, degraded and error envelopes. Unknown structures fail safely. No broad exception swallowing, busy polling, infinite retry or repeated authentication retries. Docs MCP is reference only; no execute-request or key. Test throttling/deadlines synthetically rather than deliberately exhausting live quota.

## 7. Security, privacy and visual quality

- Sensitive credentials stay in Secret Manager; ignored local config may contain nonsecret references. No payloads in examples/tests/source/history/CLI arguments/logs/builds/Terraform plaintext. Vertex/CI use IAM/ADC/WIF, no downloaded keys.
- Scope web→API, API→database/Qloo/model and deploy grants. Separate migration/runtime DB roles. Verify private API IAM externally; untrusted forwarding headers are not identity proof.
- Host-scoped secure cookies, mutation Origin checks, strict path/header allowlists, bounded bodies and ownership checks are mandatory. IDs/slugs are not authorization.
- Rate-limit search/generation/assets/model tokens with shared per-key controls across scale-out. Do not collapse all users into the web forwarding IP or trust unvalidated forwarded headers.
- Treat metadata/MCP/model content as untrusted data, never permission to alter tools, hosts or validation policy. Log safe action summaries, not raw content or private chain-of-thought.
- Server image fetches block private/loopback/link-local/metadata destinations; revalidate DNS/redirects, approve schemes/types and bound bytes/time. No unrestricted proxy.
- Follow [design.md](design.md): original cultural fight-night composition, readable titles, visible labels/focus, 48 px primary controls, contrast and keyboard/screen-reader/reduced-motion equivalents.
- No forced sound/timer/automatic advance; correctness cannot depend on colour/hover/motion/audio. Image loading/failure keeps titles readable. No dashboard/chat/agent graph as decoration.
- Inspect screenshots at 390×844, 1440×1000 and 320 CSS px plus long-title/image-failure/200%-zoom cases. Build success is not visual acceptance; axe success is not manual screen-reader proof.

## 8. Verification and release gates

Test pair/scoring permutations/ties/path exhaustion/RNG; synthetic provider envelopes/auth/deadlines/process failures; actual PostgreSQL migrations/constraints/fencing/concurrent retry/session isolation; Playwright solo/fixed replay/reload/expiry/keyboard/mobile/reduced-motion. Audit all pre-answer transports and accepted-answer recovery without future leakage.

CI uses synthetic providers, never event keys. Check relevant lint/types, OpenAPI drift, domain/provider/DB scenarios, production/container builds, secrets/dependencies and full target-page axe/browser flows. Keep full scans with realistic timeouts and writable screenshot artifacts; inspect the actual remote application-SHA result. Do not suppress failing cases or describe static Terraform validation as successful cloud deployment.

Live probes are separate/budgeted/private. Prompt 2 targets at most twelve upstream calls including retries/internal lookups; report the unproved matrix rather than exceeding it. Enabled model API does not establish project/model access. Rights, actual cross-domain ranking and five-round quality must pass before live claims.

Measure warm/cold generation/answer latency separately with samples/conditions. Performance budgets remain targets until measured; local Lighthouse is not field INP/p75. Human fun/clarity/retention needs actual consenting participants and denominators/bot/test exclusions. Agents are reviewers, not human testers.

## 9. Cloud migration, cost and retirement

Project project-bb13ecd8-9d67-408d-9a7, default asia-south1, explicit invocation scope and dedicated-resource map. Prompt 16 inventories/plans; 17 applies saved foundation; 18 publishes digests/reviews release/deploys candidate; 19 promotes; 20 retires verified legacy resources. Prompt 1 makes no cloud mutation.

Reuse accesslife-db with a new tasteduel logical DB. Keep old DB/user resources at stable/moved Terraform addresses until deliberate retirement; never rename attributes into a destructive replacement. No second billed instance for branding. Document immutable registry/bucket/state/secret names retained for cost/preservation rather than falsely claiming a rename.

Preserve remote-state bucket/prefix/ownership during app migration. Reviewed moved/import operations only: no fresh empty state, broad destroy, deletion-protection removal or unrelated PharmaGuard modification. Preserve required Qloo readers until rollback expires; copying a key is not rotation. Repository rename needs coordinated narrow WIF/remote/workflows, not owner-wide trust.

The **US$80 budget is cumulative**: AccessLife incurred cost plus pivot/shared SQL/storage/backups/models/API usage, overlap/builds/restore/currency/tax through at least **6 November 2026, 10:15 IST**, plus required follow-up. Historical US$78.48 through 5 November is not fresh headroom. Reprice before provisioning; stop if it fails. Alerts are not caps; reconcile old/new labels and unlabeled costs.

New Cloud Run first revisions cannot be assumed zero-traffic. Use controlled maintenance/IAM bootstrap or document actual restricted allocation, then candidate revisions. Tags may still be reachable at zero-percent; access is separate. Verify exact canonical/candidate origins, API audience, real browser journey and compatible rollback. Different services are not cross-product percentage splits.

Restore to a priced disposable target only; never overwrite live DB. Separate logical from managed-backup restore evidence. Pin digests and preserve recovery targets. Drain old work before retiring queue/worker/scheduler/jobs; revoke secrets/IAM only after reader/retention/rollback checks. Keep shared SQL/state/secrets protected. No automatic teardown or irreversible data deletion as cosmetic cleanup.

## 10. Completion records

Every iteration updates maintained specs and appends one or two factual dated memory lines. Report changed files, checks/artifacts, limitations and next prompt. Distinguish specs, fixture prototype, live-provider verification, local runtime, remote CI, candidate and production. Prompt 1 certifies none of the later gates.

Target freeze: 30 October; submission: 31 October 2026, 09:15 IST, subject to official recheck. Keep judging access through the reviewed window/follow-up. Prepare submission materials, but sending messages, submitting Devpost or purchasing requires separate user instruction. Do not claim unmeasured popularity or hackathon success. Teardown is deliberate after judging/follow-up and retention checks.

References collected for later recheck: [official kit](https://github.com/qloo/qloo-hackathon-kit), [MCP starter](https://github.com/qloo/qloo-hackathon-kit/blob/main/starter/mcp-client/README.md), [API access](https://github.com/qloo/qloo-hackathon-kit/blob/main/docs/API_ACCESS.md), [safe use](https://github.com/qloo/qloo-hackathon-kit/blob/main/docs/SAFE_USE.md), [terms](https://www.qloo.com/legal/terms). Current capability/rights/pricing checks belong to their numbered iterations.
