# Verification and evidence boundaries

The [release record](../infra/migration/production-release-execution-2026-10-28.md) distinguishes genuine sealed solo generation from later unauthenticated public fixed replay. Recorded checks cover Qloo ranking, Vertex tool use, five rounds, discovery saving, response-loss recovery, exact isolated replay, keyboard/reduced motion, mobile reflow, original-art OG and full axe scans.

The four-seed [quality matrix](../ai/round-quality-validation.md) checked two artist-to-film and two film-to-artist paths, each with ten distinct contestants. This is sampled technical coverage, not universal coverage or a measured surprise rate. Difficulty bands are engineering heuristics.

Tests exercise actual PostgreSQL constraints/RLS, concurrent/idempotent mutations, DTO secrecy, provider failures, contract drift and browser interactions. CI uses synthetic contracts without event keys. [Current application-source CI](https://github.com/saimaharana4/taste-duel/actions/runs/40843484745) passed for deployed source `99c23fc`; the [hotfix record](../infra/migration/production-hotfix-2026-10-29.md) binds that source to the running image digests and external checks.

## Measured samples

- One correlated cold web request: 3,361.83 ms server latency and 7,525.77 ms navigation-to-enabled-search. This is not field p75/LCP or a fully cold two-service benchmark.
- Ten warm answer-handler samples: 215.25–297.53 ms, no provider calls. This does not establish a load-tested p95.
- Monitoring: 18/18 successful points across three locations. A bounded 29-log-entry window contained four safe request errors and one admission snapshot, with no detected malformed event, credential/answer pattern or retained new request-URL log.
- Compatible rollback/return preserved all 14 inspected owner-scoped history-table hashes and original provider counters. Normal expiry was enforced; expired evidence was never extended to replay.

## Still unproven

No structured, consent-based human playtest results have been recorded; discovery value remains unmeasured. The [consent-based playtest protocol](../ai/playtest-protocol.md) measures clarity, unexpected connections, exploration interest, saves, completion and challenge value with real denominators. Agents, fixtures and successful API calls are not human playtesting.

Native screen-reader/zoom testing, managed Cloud SQL backup restore and notification delivery remain unrehearsed. Physical cleanup is manual. The logical restore establishes only its recorded scoped test. Automated axe checks do not replace human accessibility evaluation.

Natural live corrective-agent value is not established merely by a tool call and a valid pool. Correction/veto/failure paths are contract-tested; do not present synthetic corrections as live autonomous improvement or human discovery.

An LLM-only baseline can suggest familiar connections and plausible explanations. Taste Duel instead freezes the ordering actually returned for a specific Qloo request, validates comparisons and replays exact answers. Removing Qloo removes that grounding. The curator contributes bounded strategy choice; deterministic services prevent invented winners. This is a conceptual distinction, not a controlled performance experiment.
