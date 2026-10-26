# Deterministic duel pool - Prompt 7

Implemented locally on 26 October 2026. This is a private pure Python engine,
not a game endpoint, agent, live integration or deployment. Current browser
behavior remains the explicitly synthetic Prompt 4 fixture.

Prompt 8 subsequently passed this engine's real-sample gate for one genuine
artist-to-movie snapshot using the explicit HTTP adapter: 20 accepted candidates,
21 near-tie pair exclusions, 15 pool pairs and a complete five-round path.
No raw response or normalized contestant fixture was committed. See the
[curator evidence](../../ai/prompt8-curator.md); broader coverage, sourced category
diversity and live corrective strategy are not established by this sample.

## Run without credentials, database, model or network

```powershell
uv run --no-sync python scripts/tasteduel_pool_check.py --synthetic
uv run --no-sync python -m pytest -c pytest.tasteduel.ini --confcutdir=tests/tasteduel tests/tasteduel/duel_pool tests/tasteduel/duel_pool_review -q
```

The command prints aggregate facts about invented data, never real candidate
lists. Local verification lives in ignored `.data/tasteduel-prompt7/`, including
`synthetic-report.json`, `tests.xml` and `verification.json`. No new UI renders
or screenshots were required: this iteration changes no frontend code.

## Input authority and validation

`domain/duel_pool` accepts one frozen normalized context, at most twenty
candidates, and a private server RNG seed. Domain code does not import provider
SDKs, FastAPI, persistence or raw JSON. All output objects remain private.

The application bridge `prepare_qloo_pool` accepts typed QlooPort values and
confirmed seed metadata. It checks seed ID/type, the exact pinned request hash,
provenance, ordering and explicit timestamps before constructing a snapshot.
It preserves the existing zero-based provider positions by validating then
converting them to one-based domain positions. It never sets an unverified
ordering flag to true. Unknown/ambiguous/error states do not become fixture
success. Current compact MCP evidence is rejected pending its capability gate.

One-hour lookup freshness and a maximum twenty-four-hour evidence lifetime are
existing conservative product defaults, not a provider licence. The caller must
establish applicable rights and supply the permitted expiry. Expired or future
evidence is rejected, not refreshed silently. No live evidence is stored here.

Candidates must have UUID identity, a nonempty title fitting the existing
200-character API contract, matching type/context, finite numeric score and a
unique positive position. All duplicate IDs and canonically identical names are
quarantined rather than selecting the first response row. Same-name quarantine
is conservative, not proof that distinct IDs represent the same work/person.
Ambiguous identities, seed self-matches and contradictory rank order cannot win.
Missing image rights/imagery do not make an otherwise valid entity ineligible.

## Versioned quality and discovery objective

Policy `duel-pool-v1` fixes five rounds and rejects gaps at or below **5% of the
accepted snapshot's score spread**, plus exact ties. This is an explicit,
uncalibrated engineering heuristic. It is not a universal raw delta, confidence
interval, human difficulty or surprise measure. Decimal arithmetic prevents
overflow when finite inputs are near floating-point extremes. No scores are
compared across requests or domains. Threshold changes require a new policy
version; the full effective configuration and SHA-256 fingerprint accompany
each result and must be persisted later with the immutable evidence.

Distinct eligible relative gaps are divided into provisional hard/medium/easy
bands within this snapshot. Equal gaps share a band; a single observed gap does
not invent three bands. A label is private planning metadata and is not added
to the unanswered browser DTO. Human calibration belongs to Prompt 15.

The journey objective is sourced category coverage, capped at ten categories,
then gap-band variation, while maintaining a complete path. Category metadata
has bounded labels/source attribution and at most three entries per candidate.
No genre, psychology or cultural explanation is inferred from a title or score.
The current QlooPort supplies no supported categories: its bridge passes none
and reports this limitation. Synthetic category coverage proves algorithmic
behavior only. Default minima are zero categories and one band; callers may
require stricter diversity, which fails explicitly if unavailable. The agent
cannot relax those requirements or manufacture category data.

The target pool is ten to fifteen alternatives (default fifteen), where the
eligible graph permits. A complete witness is selected first; additional edges
prefer new sourced categories, contestants and bands. Fewer alternatives may
remain when coverage is sparse; the actual count is recorded, while the hard
five-round proof and quality constraints are unchanged.

## Exact feasibility, bounded optimization and presentation

Backtracking with memoization proves a matching of five disjoint edges, with
requested category/band constraints on the actual path. Five overlapping pairs
or ten candidates alone are insufficient. Path improvements seek stronger
category then band coverage using the same exact feasibility evaluator.
At most 25,000 explored states are allowed per build, shared across proof and
improvements. A limit reached before proof yields `evaluation_limited`, not a
claim of mathematical insufficiency. An objective-only limit retains an already
proven valid path and explicitly reports `objective_limited`; no optimality claim
is made. Requested hard constraints are never weakened to fill five slots.

`continuation_options` returns only edges that leave a complete policy-compliant
no-repeat continuation given previously used entities/categories/bands. Its
shared state limit raises `SearchBudgetExceeded` explicitly. This is a helper
for later adaptive gameplay, not an implemented streak/adaptation service.
Combining different snapshots later also needs global entity-ID exclusion;
this builder evaluates one context at a time.

Canonical inputs make permutation and seeded replay reproducible. Pair IDs use
a separate UUID stream assigned independently of rank/score/winner. The five
winner sides are shuffled with a 3/2 balance, not predictably alternating. Choice
IDs use an independent stream. Production callers must generate and privately
persist fresh secret server entropy; example fixture seeds are not production
seeds. IDs, RNG seed and private oriented pairs must never become generic public
serialization.

`api/pool_projection.py` projects one already selected choice into the existing
allowlisted `ChoicePublic`, with original `afterlight`/`velvet-static` fallback
assets independently of its winner. It never exposes provider URLs, score, rank,
band or another contestant. Image-rights booleans are not a licensed asset
registry. Actual current-round authorization/persistence/delivery remains
Prompt 9; no new route uses this helper in Prompt 7.

## Feedback and gate

`CuratorPoolFeedback` contains bounded enums, counts and context/policy hashes:
received/accepted/rejected candidates, rejection reason incidences, pair
exclusions, eligible/selected pair counts, supported category availability,
required/achieved diversity, path proof, evaluator limits and correction codes.
Candidate reason counts may overlap; they are explicitly **incidences**, not the
nonoverlapping public `CurationReceipt.rejection_counts` contract. Do not copy
this private tool model into browser curation DTOs. It contains no freeform
metadata, contestant IDs, future pairs, winners, affinities or hidden reasoning.

Prompt 8 may use this feedback to confirm a seed, choose another supported
target or request more candidates within provider limits, then revalidate.
Missing supported category/order capabilities can require stopping. A bounded
evaluation retry must change an eligible strategy/input or escalate explicitly;
the same deterministic input repeats the same outcome. It cannot increase
budgets, loosen thresholds, invent candidates or grant the model veto power over
deterministic eligibility/winners. No RoundCuratorAgent is implemented here.

**Real-sample gate blocked:** the [Prompt 2 record](../../ai/qloo-capability-matrix.md)
states that only aggregate feasibility metadata was retained, not reusable
normalized candidate lists. Its twelve-request budget is exhausted. Prompt 6's
MCP adapter still has `ordering_verified=false`, with compact/default-order and
score-precedence gaps. The aggregate lower bounds cannot be reconstructed into
valid snapshots or relabelled as live engine tests. No new Qloo/Vertex/Secret
Manager calls were made. A separately budgeted capability recheck must establish
actual order/type/score semantics and pass a permitted normalized sample through
the engine before claiming this gate or dependent live agent readiness.

Next numbered stage: **Prompt 8**, subject to that unresolved live gate.
