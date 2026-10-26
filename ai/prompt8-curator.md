# Prompt 8 — bounded curator implementation and evidence

26 October 2026. This supplements the historical [Prompt 2 matrix](qloo-capability-matrix.md),
the [architecture](Architecture.md) and the [execution prompt](prompts.md).
It is an implementation/evidence record, not permission to deploy or publish provider data.

## Implemented boundary

`RoundCuratorAgent` has a typed model port and five application tools:
`inspect_seed`, `fetch_ranked`, `evaluate_pool`, `finish_pool` and `stop`.
These are Taste Duel tools, not Qloo-owned agents or extra deployed services.
The model selects a verified target domain and a bounded candidate limit,
receives reason-coded deterministic feedback, and chooses whether to finish,
make one useful correction or stop. `fetch_ranked` computes feedback immediately;
`evaluate_pool` inspects that existing evaluation without another provider call.

The objective is to construct the strongest playable five-round cultural discovery
journey supported by verified Qloo evidence, balancing validity, diversity, useful
surprise potential and complete no-repeat feasibility. Surprise potential is a
product objective; numerical gaps are not measured human surprise or enjoyment.
Human discovery validation remains Prompt 15.

The model receives a confirmed seed UUID/domain, verified target-domain choices,
opaque snapshot handles and allowlisted aggregate feedback. Candidate names,
descriptions, images, scores, winners and private pairs are absent from its input.
Tool batches are schema-checked before their first external side effect. No
model output can manufacture a candidate, change a score, relax the policy or
publish a rejected pool. A second fetch requires actual inadequate feedback:
increase the candidate limit only when feedback supports that correction, or
switch to another verified target domain when supported. No demo correction is forced.

Only `finish_pool` can select a ready, five-round-validated known snapshot.
An unfinished/failed outcome does not expose a publishable `.pool`, even if an
earlier evaluation happened to be ready. Prompt 9 must additionally fence and
persist this result transactionally before any ready game response.

## Configuration and limits, fixed before live use

| Setting | Bound |
|---|---|
| Model/SDK | `gemini-3.1-flash-lite`, Google Gen AI `2.33.0` |
| Authentication/location | Explicit Vertex IAM/ADC, `global`; no Gemini API key |
| Generation | Minimal thinking, thoughts not requested, temperature 0, one candidate |
| Per-model request | 512 output tokens, at most 8 seconds, one SDK HTTP attempt |
| Overall generation | 20-second cancellation/acceptance deadline |
| Qloo | At most 6 actual upstream HTTP requests, including retries and internal lookups |
| Vertex | Normal target 2 requests; hard maximum 4 attempted requests |
| Tools/correction | 8 executed tool steps, at most 1 useful correction, repetition rejection |
| Total model tokens | 24,000 hard admission envelope; conservative UTF-8 input bounds include opaque continuation signatures |

Token admission occurs before another model request. Returned prompt/output/thinking
counts are measured separately; absent/partial usage is marked incomplete and
charged conservatively for subsequent admission. Native function-call signatures
are retained transiently for protocol correctness, never logged or persisted.
Function-call continuations are reconstructed with only the call/signature fields;
mixed thought/text fields are discarded. The response does not supply reveal copy.
Later accepted-round copy must use supported evidence or a factual higher-ranked
sentence, never an inferred psychological or causal explanation.

Cost check on 26 October: [Google Cloud standard global pricing](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing)
lists this model at $0.25 per million text input tokens and $1.50 per million
output/reasoning tokens. A conservative 24,000 input plus 2,048 output bound is
$0.009072 in model tokens, below the predeclared $0.10 iteration target. The
successful run's measured usage estimates $0.00042225 in model tokens; the
separate smoke adds $0.00007525. These are estimates, not billing verification,
tax/infra totals or a GCP spending cap. No paid grounding/search tool is enabled.
Four sequential eight-second model timeouts cannot all fit twenty seconds;
the remaining overall deadline wins, as demonstrated by failure tests. The
normal two-request path measured 5.36 seconds, not a latency percentile claim.

The pure validator has finite search bounds. Deadline checks after synchronous
validation and before publication reject late results; Python cannot preempt a
synchronous CPU instruction immediately. Cancellation propagates instead of
starting fallback or publishing after the caller has cancelled. Measured receipt
timings include actual cleanup; they are not clipped to pretend compliance.

Shared PostgreSQL admission uses the same key fingerprint across participating
Taste Duel instances. Reservations are distinct from observed HTTP dispatches;
receipts count actual dispatches. Existing AccessLife readers do not automatically
participate. **Any overlapping legacy runtime using the key must stop or adopt
the same admission boundary before a shared-key rollout.** No cloud resources or
legacy services were modified in this prompt.

## Explicit transport gap

The pinned official harness remains the default/preferred local-stdio process,
but canonical typed resolution still fails closed in this live sample. Its compact recommendation envelope drops required raw query-score
provenance/type information and exposes no explicit `sort_by=affinity` input.
Synthetic/lifecycle success cannot establish compact score precedence or ordering.

`http_ranked` is an explicit server configuration choice behind the same `QlooPort`
and request guard. It uses separately contract-tested GET/auth/allowlisted Insights
parameters, explicit affinity ordering and strict normalized `query.affinity`
provenance. It is not an automatic retry/fallback from a failed MCP result.
The separately explicit `qloo_http_typed_search=true` option uses GET `/search`
with typed parameters and strict actual-type/ambiguity validation. It accepts the
search endpoint's `{results: [...]}` envelope, which does not require Insights'
`success` field. Raw responses remain process-local. Two canonical describes
used four counted HTTP requests but returned degraded normalization; a tested
pre-harness `types[]` preservation shim did not establish live resolution. Its
source-based type-loss diagnosis is not a proven explanation of every failure.
No requested domain is accepted as evidence of an entity's returned type.

Default MCP mode remains conservative: unverified compact evidence cannot pass
the pool validator. The documentation MCP server is never a runtime data source
or credential destination.

## Execution receipts and persistence

`CurationReceipt` records actual model attempts, observed/reserved Qloo counts,
tool/status/timing facts, selected target/limit, aggregate candidates/rejections,
one-correction count, final pool/path status, policy fingerprint and versions.
Final and per-attempt reason-coded feedback stay private. Candidate reason
incidences can overlap and are not falsely summed as unique rejected entities;
legacy primary rejection counts remain empty rather than inventing an attribution. It contains no hidden thought text,
raw arguments/provider payloads, contestants, future pairs, affinities or winners.
Failed model attempts remain counted if deterministic Qloo curation ultimately
selects the pool. Fallback mode is `deterministic_qloo`, not evidence of a passed
live-agent test. Authentication failure, malformed calls and validator vetoes
never become fabricated fixture success.

These new receipt fields are in the private execution model. Existing immutable
SQL receipt columns and their read adapter have not yet been extended to persist
the complete new trace/token/feedback record. Prompt 9 owns the additive migration,
transactional pool/receipt write, fencing, retry recovery and explicitly sanitized
public summary. An in-memory receipt is not durable gameplay evidence.

## Live verification record

The separately bounded Prompt 8 smoke ledger does not reset Prompt 2's exhausted
12/12 requests. Root owns all live calls; synthetic failure tests make no provider
or model requests.

- One native-function Vertex smoke passed using the configuration above: 2,235 ms,
  241 input and 10 output tokens. This proves this project's access to that model
  and native tool calls, not a complete Qloo-grounded adaptive agent run.
- Final Prompt 8 usage: **7/8 Qloo HTTP requests, 3/5 Vertex requests**; no
  concurrency bursts or retries. Four Qloo calls were two failed canonical
  describes; one HTTP search was rejected by an initially over-strict envelope
  contract; the final typed search and real ranking used one request each.
- The genuine agent run used the previously verified artist-to-movie capability,
  selected `fetch_ranked(movie, 20)`, received real normalized Qloo evidence plus
  deterministic feedback, then selected `finish_pool` for that known ready pool.
  Two native Vertex decisions, one ranking HTTP request, 5,359 ms, 1,263 input
  and 71 output tokens; 20 eligible candidates, 169 eligible pairs, 21 near-tie
  pair exclusions, 15 selected pairs and a verified five-round no-repeat path.
  These are sample execution facts, not human enjoyment or a coverage rate.
- This closes Prompt 7's real-normalized-sample gate for this snapshot and
  establishes native tools + genuine Qloo ranking. It does **not** demonstrate
  a live corrective strategy: initial coverage was sufficient, so the model
  correctly stopped without forcing a repair. The stronger adaptive-value gate
  remains pending; future bounded tests must naturally supply inadequate real
  feedback and observe a useful repair/domain decision. Only one verified target
  domain was available in this run; live multi-domain strategy remains unproven.
- With one Qloo request left, a fresh independently resolved inadequate ranking
  plus correction cannot fit this iteration. Stop rather than renew/exceed the
  ledger. Same-domain coverage, movie-seed runtime coverage, canonical Insights
  score provenance and nested explanation/asset permissions remain gated.
- Evidence is ignored `.data/tasteduel-prompt8/{live-budget,model-smoke,live-summary}.json`.
  It contains minimal execution aggregates, never raw rows/pairs/model payloads,
  names/IDs, credentials, signatures or chain-of-thought. These are private
  artifacts, not a distributable Qloo data fixture.

The agent's implemented value is bounded strategy selection and feedback-based
repair; tests prove larger-limit and alternative-domain corrections preserve
validator authority. The live run proves stop/finish decisions and chosen
candidate limit but does not establish a benefit over the deterministic fallback.
Removing Qloo removes the game's cultural ranking evidence. Removing this agent
leaves a valid fixed deterministic strategy but removes the bounded adaptive
strategy choice; comparative discovery quality still needs Prompt 15 humans.

Synthetic tests cover malformed output, extra winner/score fields, metadata prompt
injection, repeated tools, internal request counting, eligible retry/auth handling,
deadlines, validator veto, meaningful corrective strategies and native SDK
construction. Independent grounding review checks hidden-thought stripping,
missing usage, fallback truthfulness and preventing publication after failure.
Exact final test counts/artifact paths belong in README and memory after integration.

Final offline checks: 539 full backend tests against the dedicated local database,
four Node shim tests, Ruff and application OpenAPI drift passed. The new image
builds with both pinned runtimes; network-none/read-only UID10001 checks prove
offline harness discovery, child cleanup and SDK imports without credentials.
No UI changed, so prior frontend checks were not needlessly rerun.

The browser remains an explicitly synthetic development fixture. No new frontend,
screenshots, authoritative game HTTP execution, public replay or GCP deployment
has been delivered by Prompt 8. Next numbered step: **Prompt 9**, with live
capability/agent gates resolved before dependent live integration. Prompt 8
implementation is present; its stronger live adaptive-value gate is not complete.

## Primary sources inspected

- [Official model configuration and lifecycle](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-1-flash-lite)
- [Model versions and lifecycle](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions)
- [Google Gen AI Python SDK](https://googleapis.github.io/python-genai/)
- [Official function-calling guidance](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/function-calling)

Gemini 2.5 Flash-Lite was retired before this implementation date; example names
and enabled APIs are not model-access proof. No source links grant new artwork,
provider-data retention or redistribution rights. Owned fallback artwork and the
existing conservative private-evidence/expiry policy remain in force where terms permit.
