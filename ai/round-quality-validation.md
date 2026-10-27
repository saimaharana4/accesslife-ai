# Taste Duel round-quality validation

Checked 27 October 2026, 11:07 UTC. This records a local live-provider quality inspection, not a deployment or human playtest. Related: [capability and rights matrix](qloo-capability-matrix.md), [architecture](Architecture.md), [playtest protocol](playtest-protocol.md).

## Budget and method

The predeclared ceiling was eight actual upstream Qloo HTTP requests, zero Vertex requests, sequential dispatch and no retries. Actual use was **8/8 Qloo, 0 Vertex, 0 retries**: one typed search and one opposite-domain Insights request per seed. Harness-internal lookups were avoided by using the existing, explicitly documented typed HTTP gap adapter, not by counting a workflow as one request. This does not resolve the canonical MCP resolution/order gap.

The probe also used the existing SQL per-key admission store. That store covers
participating Taste Duel runtimes on the same database; it does not prove quota
coordination with a legacy service that bypasses it. No legacy planning work or
cloud resource change was triggered by this inspection.

The existing server-side Secret Manager reference supplied the key in memory. Responses were normalized through the production provider contracts and deterministic pool preparation. No raw response, contestant catalogue, answer key or score values were saved or committed. Only minimal aggregate diagnostics were retained privately in ignored `.data/tasteduel-quality/quality-summary.json` and its bounded request ledger.

The private aggregate review artifact follows the existing 24-hour spike policy:
delete it by 28 October 2026, 11:07 UTC. Keep only this reviewed non-payload report,
the exhausted request-count ledger and synthetic contracts for reproducibility.
No new live agent correction was tested; the previously open corrective-strategy
evidence gate remains open. This matrix used deterministic validation only.

## Observed matrix

These are four particular successful requests, not a promise of coverage for every artist or film. All selected seeds resolved unambiguously in these requests.

| Chosen seed | Seed → target | Accepted candidates | Near-tie comparisons rejected | Eligible comparisons | Retained pool | Witness rounds / distinct contestants | Local probe time |
|---|---|---:|---:|---:|---:|---|---:|
| Radiohead | Artist → movie | 20/20 | 21 | 169 | 15 | 5 / 10 | 4,328 ms |
| Beyoncé | Artist → movie | 20/20 | 37 | 153 | 15 | 5 / 10 | 2,578 ms |
| Inception | Movie → artist | 20/20 | 27 | 163 | 15 | 5 / 10 | 4,390 ms |
| Spirited Away | Movie → artist | 20/20 | 14 | 176 | 15 | 5 / 10 | 4,438 ms |

Each pool had a complete five-round witness path with no repeated contestant, same-type opponents, one frozen context per comparison, verified strict ordering and balanced winning sides (two versus three). No duplicate IDs or normalized names occurred in these samples. Every witness path included all three provisional engineering gap bands. The sample covers both cross-domain directions; it does **not** demonstrate multiple target domains within one game.

Times measure these local search-plus-ranking-and-validation probes, including their network conditions. Four observations cannot establish p95 generation latency, a cold-start service target or user-perceived responsiveness.

## Artwork, explanations and quality limits

Every sample included image metadata for 20/20 candidates, but zero image reuse rights were verified. All ten witness-path presentations per sample correctly selected project-owned title-card fallback. Metadata availability does not prove image fetching/rendering or permit external artwork reuse. Provider image presentation remains gated; original artwork is the supported product presentation.

Reveals use the factual request-specific ranking template: Qloo ranked the winning entity higher for the selected seed in that frozen query. This audit does not establish richer explanation display rights or support causal, psychological or personal-preference stories. Prediction correctness is game performance; only an explicit save records a selected discovery.

No exact ties occurred in these four responses. Synthetic contracts separately prove that exact ties, near-ties and duplicate normalized names are rejected, and that missing/unlicensed imagery uses owned fallback. A lack of live ties is not proof that the provider never returns them.

The normalized port currently carries no supported sourced category metadata: all 20 candidates in every sample lacked categories. Consequently this audit cannot claim genre/category diversity. Domain coverage, distinct contestants and engineering band variation are the demonstrated forms of variation. No numeric gap is interpreted as human surprise or calibrated difficulty.

## Versioned policy decision

Retain **`duel-pool-v1`**, fingerprint `d302db4f1514bc3e0053f2b3b7a57918e56aa1cfdf83341fe650778b00ef91ad`. Its near-tie exclusion is 0.05 of the within-snapshot full score spread; bands use within-snapshot eligible-gap ordering. These are explicit engineering heuristics, not provider confidence or enjoyment probabilities. Full-range normalization can be affected by outliers.

The observed exclusion counts still left complete, nonrepeating, band-varied paths in all four cases. There is no observed output defect or consenting-human difficulty evidence that justifies changing a numerical threshold merely to report tuning. The policy was reviewed against actual outputs and retained; human calibration remains pending. Any later adjustment must receive a new policy/version, apply to new games only and preserve existing persisted pools, delivered rounds and challenge snapshots.

## Replay and human evidence

The synthetic database scenarios in [`test_challenges.py`](../tests/tasteduel/gameplay/test_challenges.py) exercise two isolated guests against frozen comparisons with independent scores, no curator calls on replay, changed/unavailable later providers and expired challenges. The affected gameplay/challenge/discovery suite was rerun: 46 passed, followed by five expanded accounting checks. These contracts establish what is tested mechanically; they are not observations of friends playing this live matrix. The implementation stores delivered rounds and sides, rather than regenerating them from current provider rankings.

**Human participants: 0. Human gate: pending.** There are no participant observations, discovery-value rates, completion rates or significant impact claims. Agents, API responses and fixture journeys cannot establish whether a reveal feels interesting rather than arbitrary. The willing-user protocol must assess clarity, cultural grounding, explicit saves, completion and challenge value with explicit denominators and consent before making those claims.

## Reproducible technical checks

Aggregate audit contracts: `uv run --project runtime/python --frozen pytest -c pytest.tasteduel.ini --confcutdir=tests/tasteduel tests/tasteduel/duel_pool/test_quality_audit.py -q` — **3 passed**. Ruff on the helper and those contracts passed. Tests use invented data, make no provider calls and assert that serialized diagnostics contain no contestant names/IDs, context or winner directions.

The live runner requires its existing explicit bounded ledger; rerunning is not permission to renew the consumed budget. Raw proprietary outputs must remain unpublished.

Final backend sweep: **681 passed, 1 skipped**. The skipped scenario requires
the separate running Compose API/restart environment; it was not exercised in
this dedicated local database run. A stale readiness migration-head check found
in the first sweep was repaired for `td0010` and passed in the final sweep.
Production build, strict TypeScript, unchanged exported OpenAPI, fixture exclusion,
Python lint, PowerShell parse, reviewed-source Gitleaks and local report/purge
checks passed. A framework TestClient deprecation warning remains; it did not
fail tests. New changes have not been pushed or verified by remote CI.

The affected production-build keyboard browser journeys passed solo and fixed
replay at 1440×1000, 390×844 and 320px: six journeys, 33 full unexcluded axe scans
with no violations, and 33 captures. Reviewed captures include the mobile result,
desktop result and 320px reveal, with loaded fonts, readable long titles and
visible focus. All content in those browser checks is explicitly synthetic;
the four live quality probes above are separate evidence. Screenshots remain
ignored under `test-results/tasteduel-prompt13/`. These checks do not establish
human screen-reader testing or human enjoyment.
