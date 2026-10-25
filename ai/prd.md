# Taste Duel product requirements

Revision 3 - 25 October 2026 - Prompt 4 development fixture journey; live-product requirements remain targets

## Delivery status and authority

Taste Duel is the selected new product. This document defines full-product requirements. Prompt 4 implements a complete five-round development fixture frontend, following Prompt 3's original visual prototype. The Python backend and GCP deployment remain AccessLife. Old venue checks and the old live URL do not validate this game. No database migration, repository rename or cloud change occurred in Prompts 3–4.

The execution sequence is [prompts.md](prompts.md). Use [Architecture.md](Architecture.md), [rules.md](rules.md), [design.md](design.md) and [phases.md](phases.md) together. Record actual results separately in [memory.md](memory.md). Preserve the original three reference files unchanged; their legacy planner requirements do not govern this pivot.

Prompt 2's [capability record](qloo-capability-matrix.md) establishes sample raw artist→movie and movie→artist numeric five-pair feasibility, not general coverage or game quality. Canonical MCP Insights and same-domain cells remain unverified within the exhausted twelve-request budget. Prompts 3–4 add no live calls. The fixture now computes a score from five accepted invented answers and supports optional local discovery saves; it is in memory, fixed rather than adaptive, and resets on refresh. Its invitation previews the five played rounds without creating a public link or friend replay. These checks do not pass the live functional requirements below.

**Current fixture contract:** explicit development mode only; fictional seed confirmation, preparing/submitting locks, accepted reveal, manual Next, computed n/5 result and local invitation. “Why this duel?” appears only after acceptance and identifies synthetic evidence, never Qloo output. A compact fixture-labelled curation summary exposes only aggregate preparation facts. No causal explanation, taste diagnosis, future contestant, affinity value or private reasoning belongs in these disclosures. Prediction correctness measures game performance; only the chosen seed and explicit saves are user-selected discovery signals.

## 1. Product and problem

**Choose one favourite, predict five Qloo comparisons, discover something surprising, then challenge a friend to the same five rounds.**

Taste Duel makes cultural connections playable. Rather than browsing another recommendation list, a guest predicts between two recognisable choices and sees which ranks higher for the selected seed in a frozen Qloo request. The intended benefit is entertaining discovery and a simple shared challenge, not psychological assessment.

Core question: **“Which ranks higher for this seed in Qloo's taste graph?”** A player predicts an aggregate ranking. Their own preferences are never right or wrong. Affinity is not a probability of individual enjoyment, proof of causation or universal cultural truth.

| Audience | Job | Product implication |
|---|---|---|
| Music and film fans | Find an interesting connection quickly | One favourite, large visual choices, immediate reveal |
| Friends | Compare predictions on the same questions | Fixed five-round snapshot, actual score, guest replay |
| Qloo developers and judges | See cultural intelligence cause a product decision | Genuine Qloo ranking determines answers; bounded agent decisions are inspectable |

Enjoyment, discovery value and repeat use are hypotheses until observed with real participants. API success, Codex review and synthetic playthroughs are not human validation. No worldwide uniqueness claim is made.

## 2. MVP scope

- Mobile and desktop browser application, guest play, no signup wall.
- Typed entity search and explicit disambiguated selection. Music-artist and movie seeds, with movie/music-artist target rounds, are subject to live capability checks. A director/person is not silently treated as a film.
- Five solo rounds selected adaptively from a bounded precomputed pool; no contestant repeats in a played game and the seed cannot oppose itself.
- Server-authoritative answers, one point per correct prediction, maximum five. Optional streak; no speed bonus or fake percentile.
- Artwork-led choices, immediate pressed feedback, grounded reveal, explicit Next and a shareable result ticket.
- Guest discovery save/unsave with clear expiry.
- Challenges freeze the creator's actual five played rounds, order, side positions, contexts, answers and scoring version. Friend replay is fixed rather than independently adaptive.
- Honest insufficient-coverage, provider-failure, interrupted-game, expiry and artwork-failure states.
- One bounded `RoundCuratorAgent`; deterministic services own validation, winners, scoring and replay.

Accounts, public leaderboards, monetary prizes, personality diagnosis, native apps, social feeds, chat, bookings, maps, transport, accessibility routing and multi-city planning are outside this MVP. Book/person seeds and book rounds need separate coverage/metadata gates. No RAG corpus, ingestion, embeddings or new vector service is required.

## 3. User journeys

### Solo

1. Understand the game from the opening screen; search for a favourite artist or film.
2. Select a real entity with visible type/identity metadata.
3. Start a game and see truthful preparing status while the server commits a validated private pool.
4. Predict between two same-type choices without receiving hidden ranks, affinities or answers.
5. Read the accepted reveal, optionally save a discovery and select Next.
6. Finish five rounds; see the actual score, discoveries and share/replay actions.

### Friend challenge

A completed creator game produces an unguessable link with explicit expiry. Another guest sees the seed and creator score, then plays the exact same five comparisons in the same order and sides. Compare scores only for that challenge/version. Changed upstream rankings never change its answer key; expired evidence expires the challenge instead of silently refreshing it.

### Recovery and clearing

Refresh restores the saved current state, including an accepted reveal. Lost creation/answer/Next responses reconcile with saved state without extra games or points. A creation retry retains its idempotency key for the same input; conflicting reuse fails. Clearing a session revokes its owned private games and challenges under the documented policy; it does not retroactively rewrite backups. Expired state offers a fresh game, never another guest's records.

## 4. Functional acceptance requirements

Every acceptance criterion below is a **future gate**, not a pass recorded by this specification.

| ID | Requirement | Acceptance criterion |
|---|---|---|
| FR-01 | Guest launch | A fresh browser reaches gameplay without signup; session clearing revokes owned private access. |
| FR-02 | Typed seed search | Real IDs/types and useful identity metadata; ambiguous results require selection; stale responses cannot overwrite a newer search. |
| FR-03 | Qloo evidence | Each pair has same-type contestants from a single verified affinity-ordering context, timestamp and immutable evidence reference. |
| FR-04 | Cross-domain experience | The release path demonstrates genuine cross-domain rounds. Musician-to-musician results alone do not establish this capability. |
| FR-05 | Complete pool | Generation proves a five-round path without repeated contestants, not merely five pairs that exhaust each other. |
| FR-06 | Pair validation | Reject self/duplicate/ambiguous entities, ties/near-ties, missing required metadata, nonfinite scores and contradictory ordering under a versioned verified policy. |
| FR-07 | Adaptive solo | Select unused saved pairs using versioned heuristic difficulty; scarce-band fallback is explicit and existing winners never change. |
| FR-08 | Authoritative answer | Transactional ownership/state/one-answer checks; identical duplicates return the accepted answer, conflicts fail. |
| FR-09 | Honest reveal/score | Expose only the accepted round's evidence; recompute actual score from saved answers. No fabricated percentile or client total. |
| FR-10 | Explicit advancement | Next is sequential/idempotent and cannot skip an unanswered round; refresh restores current accepted reveal or unanswered state. |
| FR-11 | Exact challenge | Two isolated sessions replay the creator's exact five rounds/order/sides/rules with zero Qloo/Vertex calls. |
| FR-12 | Safe sharing | Invitation/OG contain only permitted seed/title/actual score and rights-cleared art, without future choices, private answers or session data. |
| FR-13 | Discoveries | Session-owned save/unsave, useful empty/expired states and evidence/session retention; no inferred personal preference claims. |
| FR-14 | Durability | Creation/answer/advance duplicates, lost responses, fenced lease expiry, restart, competing tabs and clearing during generation preserve correct state. |
| FR-15 | Provider honesty | Distinguish genuine agent-curated Qloo, deterministic Qloo curator and development fixtures; insufficient coverage never becomes invented gameplay. |
| FR-16 | Inclusive flow | Keyboard, screen-reader-oriented semantics, reduced motion, 200% zoom and 320px reflow; no reliance on sound/colour/animation. |
| FR-17 | External release | Public GCP web app and licensed public source match the verified release SHA; direct unauthenticated private API access is rejected. |

## 5. Fairness, secrecy and semantic limits

Both contestants share target type and request context. The five rounds may use several independently frozen domains; never compare movie scores to artist scores or mix values across queries. At least one tested round must genuinely cross domains relative to its seed. Determine actual wire units/ordering during capability work; do not convert example values into enjoyment percentages. Difficulty bands are game heuristics, not calibrated Qloo confidence or human win probabilities.

Public side order is independent of upstream rank; IDs are opaque. `PlayableRoundPublic` omits winner, ranks, affinities, revealing explanation and future pool. `RevealedRoundPublic` may expose only an accepted answered round after ownership/state checks. The boundary covers JSON, HTML, RSC, scripts, prefetch, answer-dependent URLs, analytics and OG output.

Qloo/LLM requests are forbidden during answer acceptance and Next. Preserve challenge evidence and rule versions; never re-query to repair an expired snapshot. Shared challenges are casual games, not cheat-proof competitions: prior knowledge, external research and repeated attempts remain possible. Scores from unrelated adaptive games are not comparable as equal tests.

## 6. Data, artwork and agent boundaries

| Source/component | Role | Gate |
|---|---|---|
| Official pinned Qloo harness | Resolve entities; rank candidates; supported explainability/metadata | Inspect real tools, limits, semantics, permissions and cross-domain coverage |
| Original CSS/SVG/title artwork | Fallback covers, branding, safe social cards | Retain sources/font licences; never impersonate real promotional art |
| Optional TMDB | Film metadata/artwork enrichment | Verify credentials, terms, attribution and separate social-reuse permission |
| Optional Wikidata | External IDs/type/date enrichment | Bounded queries and matching provenance |
| Optional Commons | Small rights-cleared image set | Check each file's licence, attribution and additional restrictions |
| Vertex `RoundCuratorAgent` | Bounded tool choices and optional grounded copy | Verify model access; deterministic validators can veto |

An image field is not permission to mirror, transform or publish that artwork in a social card. Missing rights lead to an intentional original title card. No Google Images/Letterboxd scraping, mandatory Spotify OAuth or fake real-film posters.

Use private bounded caches. The dated [Qloo/source capability matrix](qloo-capability-matrix.md) records inspected terms, bounded operational defaults and any unresolved event restrictions for raw responses, minimal entities, immutable snapshots, challenges, logs and backups. No universal contractual numerical TTL is established by the inspected guidance; product defaults are not licence grants. Challenge lifetime cannot exceed its evidence permissions.

The agent can choose supported targets, request bounded data and propose valid pairs. It cannot create affinities, winners, candidates or causal explanations, or override validator rejection. Vertex failure may use a transparently labelled deterministic curator with genuine Qloo data; this is not a passed live-agent execution. A fixed pipeline narrated by an LLM is not automatically autonomous reasoning.

## 7. Quality targets and verification

| Area | Target evidence |
|---|---|
| Visual | Inspected 390×844, 1440×1000 and 320px screenshots, long titles and failed images; build success alone is insufficient. |
| Accessibility | Full axe/keyboard/reduced-motion/reflow/contrast checks; no unresolved serious/critical defects. Report actual manual screen-reader checks separately. |
| Performance | Lab LCP ≤2.5s/CLS ≤0.1; initial route JS about ≤180KB gzip/gameplay addition ≤100KB targets; pressed feedback <100ms; warm answer-handler p95 ≤500ms target. |
| Generation | Target about 20s; ≤6 upstream Qloo requests including retries/harness lookups; normal 2 Vertex requests, hard max 4, with measured step/token/cost limits. |
| Security | Session/mutation-origin isolation, secure cookies, private API IAM, safe bounded image fetching, prompt-injection resistance and no secret/pre-answer leakage. |
| Reproducibility | Node 24/Python 3.12 compatible pins/locks, clean migrations/container restart and actual remote CI for the application SHA. |
| Recovery | Actual local persistence and priced disposable restore checks; logical and managed Cloud SQL restore are distinct claims. |

Targets remain unmeasured until implemented. Report sample sizes/network/cold-start conditions; Lighthouse cannot establish field INP/p75, and scans cannot establish zero risk or user enjoyment.

## 8. GCP delivery and constraints

Plan public Next.js Cloud Run web, private FastAPI API, PostgreSQL 16 on the existing dedicated SQL instance, a migration job, scoped Secret Manager and Vertex IAM. One application agent does not require separate deployed agent services. No second billed SQL instance merely for branding.

Project `project-bb13ecd8-9d67-408d-9a7`, default region `asia-south1`, is an input to re-inventory, not a new live check. New `tasteduel` logical data/identities stay separate from preserved AccessLife data. Retain Terraform ownership and rollback. Immutable physical names may remain documented legacy exceptions. Repository/WIF migration, provisioning, cutover and retirement occur only in their selected later prompts.

The **US$80 total incremental envelope includes AccessLife cost already incurred**, remaining shared resources, pivot/overlap, models, builds, restore checks, currency and tax. The historical US$78.48 forecast is not new headroom. Reforecast through at least **6 November 2026, 10:15 IST**, plus required follow-up. Alerts are not caps; provisioning stops if the refreshed estimate fails.

## 9. Later work and success evidence

After the reliable core journey: additional domains/languages, richer permitted explanations, optional accounts for longer-lived discoveries and experimentally justified difficulty tuning. Do not add accounts/social features before proving the game is enjoyable.

Measure real completion, replay, challenge completion and discovery saves with explicit denominators/test exclusions, minimal first-party events and retention. Observe willing users with consent. No participants means human impact is pending; never invent popularity, testimonials or retention.

Target feature freeze: **30 October 2026**. Target submission: **31 October 2026, 09:15 IST**, subject to official-rule recheck. Preserve judging access through **6 November 2026, 10:15 IST** and required follow-up within refreshed cost review. Preparing materials does not authorize sending/submitting them.

The MVP is complete only when a guest uses the real GCP app to select a supported real seed, finish five valid Qloo-backed rounds, see the actual score, save a discovery and create an identical friend replay, with visual/accessibility/security/recovery evidence and truthful operations documentation. After Prompt 4 this remains a live-product target; synthetic local play does not complete it.
