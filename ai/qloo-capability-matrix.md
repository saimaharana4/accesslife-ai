# Taste Duel — Qloo capability, source and rights matrix

Research date: **24 October 2026 (IST)**. Scope: **Prompt 2 only**. This is a feasibility record, not a game implementation, packaged production adapter, deployed agent or infrastructure change.

**26 October follow-up:** [Prompt 8's separate evidence record](prompt8-curator.md)
adds one validated real artist-to-movie pool and genuine Vertex tool use within
a separate 7/8 Qloo, 3/5 Vertex ledger. This historical Prompt 2 budget remains
12/12. Canonical resolution and live corrective strategy remain unverified.

**Result: partial capability gate.** Official-source research, offline MCP discovery and two live cross-domain raw-HTTP samples passed. The 12-request ceiling is exhausted. Both artist and movie seeds have a demonstrated five-round numeric pool path, but the canonical MCP Insights path and same-domain cells remain unverified. Only independent synthetic visual work in Prompts 3–4 may proceed before those dependent integration gaps are resolved. No Taste Duel application or GCP migration is complete.

## 1. Reproducible official-source pins

| Source | Inspected immutable revision |
|---|---|
| [Official hackathon kit](https://github.com/qloo/qloo-hackathon-kit/tree/80a82b26413142c6d60a71203d51836a2e708cf2) | `80a82b26413142c6d60a71203d51836a2e708cf2` |
| [Official public documentation](https://github.com/qloo/docs-public/tree/d4a0eb978518f7fb404993d1509d11b21239ada6) | `d4a0eb978518f7fb404993d1509d11b21239ada6` |
| [Npm package metadata](https://registry.npmjs.org/@qloo/qloo-harness/0.1.26) | `@qloo/qloo-harness@0.1.26`; declared Node `>=22.19.0` |
| [Package tarball](https://registry.npmjs.org/@qloo/qloo-harness/-/qloo-harness-0.1.26.tgz) | SHA-256 `95529b2ac520450e5a2c9701a9baa1d2eccf52f15ccd6ef408aec86397d13ed6` |
| Tested local Node | `24.18.1`; isolated harness installation under ignored `.data/` |

The harness software is MIT licensed; that does not license Qloo output or external artwork. Project lockfiles/runtime dependencies have not been replaced in this feasibility iteration.

Exact Git blobs inspected:

| Pinned file | Blob SHA |
|---|---|
| Kit [`docs/API_ACCESS.md`](https://github.com/qloo/qloo-hackathon-kit/blob/80a82b26413142c6d60a71203d51836a2e708cf2/docs/API_ACCESS.md) | `1699c7dde6fa7880577206b04e4bd35bd6280237` |
| Kit [`docs/SAFE_USE.md`](https://github.com/qloo/qloo-hackathon-kit/blob/80a82b26413142c6d60a71203d51836a2e708cf2/docs/SAFE_USE.md) | `d44399d14a7165b6a9cebe7b118a1f0eb73dba57` |
| Kit [`starter/mcp-client/README.md`](https://github.com/qloo/qloo-hackathon-kit/blob/80a82b26413142c6d60a71203d51836a2e708cf2/starter/mcp-client/README.md) | `373832545c663179f29f6381de4b5444003e0593` |
| Kit [`manifest.json`](https://github.com/qloo/qloo-hackathon-kit/blob/80a82b26413142c6d60a71203d51836a2e708cf2/manifest.json) | `a2919cf7bbb6561c35f9c98cd19f694e381cf26e` |
| Docs [`reference/available-parameters-by-entity-type.md`](https://github.com/qloo/docs-public/blob/d4a0eb978518f7fb404993d1509d11b21239ada6/reference/available-parameters-by-entity-type.md) | `48caf4b440b55cc179f2fca648d35c05b03abadd` |
| Docs [`docs/interpreting-affinity-scores.md`](https://github.com/qloo/docs-public/blob/d4a0eb978518f7fb404993d1509d11b21239ada6/docs/interpreting-affinity-scores.md) | `a6b241f7d9bd0b9725e63ad5c108b2171a417c04` |
| Docs [`reference/insights-api-deep-dive.md`](https://github.com/qloo/docs-public/blob/d4a0eb978518f7fb404993d1509d11b21239ada6/reference/insights-api-deep-dive.md) | `4ec376b4776f24523c5ab0bc76d80cd2ce0edf55` |
| Docs [`openapi-schema.json`](https://github.com/qloo/docs-public/blob/d4a0eb978518f7fb404993d1509d11b21239ada6/openapi-schema.json) | `468bc7e5f5ac566a294ad7fd76f9244375690ab3` |

### Advertised OpenAPI download: rejected as an endpoint contract

The pinned `openapi-schema.json` is an OpenAPI **validation meta-schema**, identified by `$id=https://spec.openapis.org/oas/3.1/schema/2022-10-07`. It has no API endpoint `paths` and no top-level `openapi` version declaration. Do not generate a Qloo client from it. Use inspected reference content and actual discovered tool schemas; the future application generates its own web types from FastAPI OpenAPI.

## 2. Offline harness discovery and transport boundary

Canonical MCP initialize, `tools/list` and `qloo_capabilities` completed with networking disabled: **zero upstream Qloo requests**. The observed contract is `1.0.0`, checksum `sha256:762bdcc5e14ff797b6de739d2658a83f78af35e68d7a5a3449455be6046924f5`, exposing ten tools including capabilities. This proves local discovery/readiness, not live API authorization or every advertised domain.

| Surface | Verified shape or limit | Taste Duel consequence |
|---|---|---|
| `qloo_describe` | Required `entity`; optional `type` | Typed confirmation; ambiguity remains explicit |
| `qloo_recommend` | Required `target_type`; optional signals, explain and bounded filters; `limit` 1–20, default 10 | Request a small pool, inspect returned metadata/order |
| `qloo_rank` | Required `options`, `option_type`; at most ten options | A 20-candidate pool cannot be reranked in one rank call; do not merge different batch scores into one comparison context |
| Entity/tag arrays | 1–10 items; strict input schemas | Do not pass unknown raw API parameters as MCP arguments |
| Image/explainability controls | Recommend exposes explainability but not `filter.exists` or `sort_by` | Raw API documentation is not the harness input contract |
| Target enums | Artist, book, brand, movie, person, place, podcast, TV show, videogame advertised | Only live-probed seed/target combinations gain feasibility status |
| Lookup costs | Names may require search plus details; a cold UUID may still hydrate `/entities` | Count actual HTTP requests, not just tool invocations |

The official data MCP is local stdio. Documentation MCP is reference-only. The stock CLI's event-host configuration requires both `QLOO_BASE_URL` and matching `QLOO_TRUSTED_BASE_URL` set to `https://hackathon.api.qloo.com`; no fallthrough to the production host. The inspected probe instead explicitly injects that base URL with `allowCustomBaseUrl: true` into QlooClient.

The spike uses the official canonical server/tools with an injected pinned QlooClient configured for one attempt and a bounded timeout. This is not a claim that the stock CLI's defaults were tested unchanged. Package defaults of three attempts, 20-second per-attempt timeout and potentially long retry delay cannot establish the game's 20-second overall target.

## 3. Live request budget and capability results

Hard ceiling and actual count: **12/12 upstream Qloo HTTP requests for this iteration**, including search, hydration, Insights and retries. The spike agent was the sole initial owner; after its interruption, the lead took over only the four remaining sequential requests against the same persistent ledger. No concurrent owners or budget reset. All twelve responses were HTTP 200; no retries. Vertex is deferred to Prompt 8: **zero model calls**.

The transport guard reserves each request in an ignored persistent ledger before dispatch, permits only sequential GETs to the event host, disables automatic redirects/retries and rejects a thirteenth request. It must account for harness-internal work. Only allowlisted quota/expiry metadata and minimal aggregate evidence may persist; never credentials, whole response bodies or a mirrored catalogue.

| Probe | Actual evidence and limits |
|---|---|
| Artist seed → movie target | Raw diagnostic: Radiohead exact typed seed; 20 unique movie candidates, finite descending `query.affinity`, 20 distinct values. Five disjoint comparisons feasible in this sample |
| Artist seed → artist target | Unverified; no Insights request for this cell within the budget |
| Movie seed → movie target | Unverified; no Insights request for this cell within the budget |
| Movie seed → artist target | Raw diagnostic: Inception exact typed seed; 20 unique artist candidates, finite descending `query.affinity`, 20 distinct values. Five disjoint comparisons feasible in this sample |
| Typed search / ambiguity | Canonical typed describe of Radiohead, Inception and Phoenix returned `ok`, one compact entity each; exact domain validation initially rejected compact metadata loss. Raw typed searches uniquely matched the first two using `types[]`. Untyped signals for those names returned `needs_input`; no guess was made. Phoenix is not a general ambiguity-coverage claim |
| Canonical MCP recommendation | Four workflow calls returned `needs_input` and reused two lookup outcomes; **no canonical MCP live Insights success**. Offline schema discovery and live describe success are separate evidence |
| Wire units, order and ties | Both raw samples used `query.affinity`, no top-level contestant affinity; observed decimal values within 0–1, descending when explicitly sending `sort_by=affinity`, no exact ties. No universal scale or default MCP ordering established |
| Images | `properties.image` present for 20/20 candidates in each sample; URL fetches, licence, image dimensions and actual rendering unverified |
| Explanations / warnings | Per-entity and global explainability fields present in both samples; top-level warning arrays absent/empty. Nested explainability warnings, content grounding and influence semantics were **not inspected** and remain gated |
| Five-round numeric feasibility | Extreme-pair lower bound at raw epsilon `0.01`: 6 artist→movie and 5 movie→artist disjoint pairs; at `0.001`: 9 each. These are sample sensitivity checks, not adopted game thresholds or quality/adaptive-engine validation |
| Book/person | Not probed; disabled until a separate budgeted coverage/metadata check |
| Quota / key expiry | No captured quota/rate-limit/expiry headers on the twelve responses; inspected published guidance gives no numerical total or key-expiry date. Absence does not imply unlimited use or indefinite permission |

Request accounting (persisted reservations, including harness internals):

| Ordinals | Transport and operation | Requests |
|---|---|---|
| 1–6 | Canonical MCP typed describe: each of three names triggered `/search` then `/entities` | 6 |
| 7–8 | Canonical recommend with untyped named signals: two `/search` lookups, then ambiguity cached for the second target | 2 |
| 9–10 | Explicit raw diagnostic `/search`: exact typed Radiohead/artist and Inception/movie | 2 |
| 11–12 | Explicit raw diagnostic `/v2/insights`: artist→movie and movie→artist | 2 |

The last four calls are an explicit diagnostic escape hatch, **not** a silent fallback or proof of production MCP integration. GET Insights sent only `filter.type`, resolved `signal.interests.entities`, `take=20`, `feature.explainability=true` and `sort_by=affinity`. Search sent `query`, typed `types` and `take=5`. Host trust was explicit; no unknown category parameters or image filter were passed.

Search's `types[]`, Insights' subtype and the harness interpretation's typed identity require deliberate normalization. Compact results can omit type metadata: use matching resolved-identity context, never invent a domain or accept a contradictory one. The initial validator error consumed the first six requests without preserving reusable IDs; that is a probe limitation, not evidence of API denial. The final two cross-domain responses resolve data feasibility without hiding this harness integration gap.

Ordinary HTTP `Expires`, if returned in a later probe, would describe cache freshness; it must not be presented as credential/permission expiry without documented provider semantics. No key quota exhaustion or live 429 was attempted.

The sample matrix will not establish coverage for every artist/movie. No additional requests are justified merely to remove a caveat. Test 429, timeouts and malformed data synthetically; do not exhaust a credential to prove throttling.

## 4. Score and game interpretation

The pinned score guide discusses 0–100 normalized presentation; these two wire samples instead returned decimal `query.affinity` within 0–1. Do not automatically multiply values or assert every endpoint/version uses that range. Explainability input-influence values are separate from contestant affinity. Preserve the exact field, raw value, query context and version; prefer relative rank wording and never describe an affinity as individual enjoyment probability. If top-level and nested affinity both appear and disagree, reject the conflict rather than mix precedence.

Both contestants must come from one verified affinity-ordering response with the same seed/signals, target, filters and retrieval context. Reject equal/near-equal scores under an explicit versioned game heuristic, contradictory ordering or missing required scores. Do not use arbitrary ID/name/list tie-breaks to manufacture an answer. Raw scores from different requests/domains are not comparable.

Five rounds require a matching of at least five edges in the valid-pair graph: vertices are unique contestant IDs and edges are eligible comparisons. Ten candidates alone do not prove this, nor do five overlapping pairs. Adaptive selection must preserve a matching large enough for the remaining rounds. Separate target/context pools can supply independent rounds with global entity-ID no-repeat checks across their union, but cannot create cross-domain score comparisons.

A numeric near-tie threshold and difficulty bands are engineering/game choices. Sensitivity checks can establish whether a sample has enough distinct pairs; they do not calibrate human difficulty, statistical confidence or repeat-use value. No LLM chooses or writes winners.

The spike's sorted-extremes greedy routine reports a **constructive lower bound**, not maximum matching. A bound of five establishes five disjoint pairs under its stated filters; a lower value cannot prove insufficient coverage. Production pool construction still needs a validated matching/selection policy and no-repeat adaptive path in Prompt 7. No particular pair or answer key from the live samples is committed.

## 5. Source, artwork and rights decisions

| Source | Allowed role in the MVP | Current decision and remaining condition |
|---|---|---|
| Qloo | Identity and aggregate request-specific rankings; supported returned explanation | Sole ranking authority. Minimal server-side evidence, no public raw-response endpoint/catalogue export |
| Original SVG/CSS/typographic art | Covers, branding and social previews | Complete practical fallback; own the artwork and retain actual font licences when selected |
| Qloo image metadata | Optional image reference | Presence is not a display/mirroring/transformation/social licence; do not fetch or ship artwork without established usage rights |
| TMDB | Optional exact-matched film metadata/art | Separate key/terms/attribution review; no need to enable it to build the game |
| Wikidata | Optional structured entity matching | Structured entity data is CC0; linked media is not automatically CC0 |
| Wikimedia Commons | Optional selected images | Per-file licence/creator/source/changes and other applicable rights; do not assume all media share one licence |

The [event API access guidance](https://github.com/qloo/qloo-hackathon-kit/blob/80a82b26413142c6d60a71203d51836a2e708cf2/docs/API_ACCESS.md) permits caching needed for a project and discourages bulk graph recreation. It specifies no universal numerical retention period. The harness's own resolution-cache defaults are implementation behavior, not a licence grant.

[Qloo public terms](https://www.qloo.com/legal/terms) incorporate additional agreements and reserve Qloo/third-party rights. Do not misread restrictions on website content as an explicit blanket ban on all permitted API caching. No bespoke credential email/event agreement was supplied to this review beyond the known API access details. Exact additional restrictions, total quota and permission expiry remain unresolved unless returned/documented metadata establishes them.

Optional-source references: [TMDB FAQ](https://developer.themoviedb.org/docs/faq), [Wikidata licensing](https://www.wikidata.org/wiki/Wikidata:Licensing), [Commons reuse](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia). TMDB's applicable noncommercial/commercial treatment and attribution do not automatically clear every linked asset or social reuse. Commons reuse can proceed under the actual file's licence where its conditions are met; additional rights may still matter.

No new external-artwork credentials, OAuth flow or scraping service is required. Original title cards keep the core game independent of optional image-rights gaps. Do not substitute invented images claimed to be authentic film posters.

## 6. Minimal retention and challenge policy

These are **conservative product defaults**, not numerical Qloo contractual allowances. They implement minimal project-needed caching under the inspected event guidance and remain subject to any applicable additional terms:

| Data | Proposed maximum and rule |
|---|---|
| Raw live response | In-process only; no raw capture file, Git fixture or public endpoint |
| Private spike aggregates | Delete after evidence review, within 24 hours of this spike; no candidate list or raw response. Public source pins/tool schemas and synthetic tests can remain. This is an operational default, not a contractual retention grant |
| Normalized lookup/candidate cache | One hour maximum, private, scoped by query/provider/version |
| Game/challenge evidence | 24 hours maximum; retain only contestant identity, query fingerprint/context, verified rank/winner, minimal pair score/observed scale/order evidence needed for tie audit/reveal, times and versions; no full response |
| Challenge expiry | No later than evidence/game expiry or known earlier permission termination/revocation; no silent reranking |
| Analytics | Minimal aggregate counters with separately documented retention; no raw entity/seed payloads or persistent fingerprints |
| Backups/logs | Explicit operational retention; restore must purge/reconcile expired/revoked evidence before serving it |

Use a bounded cleanup path, private storage/access and logical expiry checks even if a physical backup has not aged out. Session clearing/revocation affects live access; it does not instantly rewrite backup history. A shared challenge exposes only the limited game interaction, not a raw snapshot download. Do not infer indefinite permissions when key expiry metadata is absent.

Original-art prototype work is not blocked by optional media rights. Genuine unresolved event restrictions must be recorded and resolved before a use they prohibit; do not invent a mandatory approval ceremony where the published terms already permit the use.

## 7. Evidence, tests and next gate

Evidence: ignored `.data/qloo-prompt2/ledger.jsonl`, `responses-meta.jsonl`, `offline-contract.json`, `capability-summary.json`, `capability-continuation-summary.json` and `raw-capability-summary.json`. They contain public tool schemas or minimal aggregate capability metadata; no raw responses, candidate names/IDs, answer pairs or secret payload files were saved. The Secret Manager payload was used server-side in process only; cloud resources were not provisioned or changed.

Committed source: [bounded probe](../scripts/taste_duel_capability_spike.py), [synthetic tests](../tests/contracts/tasteduel/test_capability_spike.py) and [invented ranking fixture](../tests/contracts/tasteduel/synthetic_recommend.json). The probe is an isolated diagnostic, not a reusable runtime adapter. Its private ledger is intentionally not distributed: do not interpret a clean clone as permission to restart this iteration's consumed live budget.

Reproduce **offline only** (Node 24; the existing uv environment supplies Python dependencies):

```powershell
npm install --prefix .data/qloo-prompt2/harness --no-save --ignore-scripts --package-lock=false @qloo/qloo-harness@0.1.26
uv run python scripts/taste_duel_capability_spike.py
uv run pytest --confcutdir=tests/contracts/tasteduel tests/contracts/tasteduel -q
uv run ruff check scripts/taste_duel_capability_spike.py tests/contracts/tasteduel
```

Package-dependent tests skip if the isolated pinned package is absent; they do not install or fetch live data automatically. Synthetic contracts exercise valid/malformed responses, authentication failure, 429, timeout, exact GET/auth construction, request ceiling/serialization, unsafe endpoint rejection, ambiguity, missing/nonfinite/tied scores and typed normalization. These do not prove live throttling, retries, game durability, UI accessibility or model access. Final test totals are recorded in memory/README.

**Remaining probes, requiring a separately agreed small budget:** (1) typed user-selected ID through canonical recommend to Insights, counting cold UUID hydration and confirming default affinity ordering/type context; (2) artist→artist and movie→movie candidate feasibility; (3) permitted minimal nested explanation-warning/influence inspection. Reuse in-process resolution only where the pinned contract supports it. Book/person checks are optional later. Obtain numerical quota/key-validity details from provider metadata or applicable account/event terms when available; do not infer them. Vertex access stays deferred to Prompt 8.

Do not proceed from a partial/failed live capability cell to a claimed successful integration. Independent labelled fixture UI work may proceed in Prompts 3–4 if a provider gate is blocked. The complete game, deterministic engine, real agent, packaged adapter, recovery behavior and GCP deployment remain later prompts even when a sample proves data feasibility.

Related: [architecture](Architecture.md), [requirements](prd.md), [rules](rules.md), [phases](phases.md), [design](design.md), [memory](memory.md), [execution prompts](prompts.md).
