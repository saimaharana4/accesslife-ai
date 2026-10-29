# Taste Duel Qloo integration runtime

The backend packages official `@qloo/qloo-harness@0.1.26` with Node 24.18.1 and its complete lockfile. Dependencies are installed at build time, never during application startup. The MCP tool manifest is pinned in `discovered-contract.json`; it is not an upstream endpoint OpenAPI contract or a source for browser type generation.

## Actual transport

The recorded production integration uses explicit typed HTTP search and `http_ranked` GET Insights behind QlooPort. This preserves returned type evidence and verified within-request affinity ordering. It is a documented adapter choice, not a silent fallback after authentication failure. The packaged canonical MCP path remains implemented/contract-tested; its presence does not prove live MCP ranking success.

Raw HTTP and MCP requests share the same bounded request policy and database-backed key admission. One MCP workflow may perform multiple upstream lookups. Count dispatches/internal resolution/retries, not merely tool invocations. Authentication and malformed-contract failures fail closed rather than fabricating candidates or switching providers.

## Process boundary

The Python lifecycle owns one managed local-stdio process per API instance when MCP is enabled. Startup initializes/discovers and verifies allowlisted schemas. Only capabilities, describe and recommend workflows are allowed. The runner uses the official client/tool implementation with bounded bodies, deadlines, event-host GETs and manual redirect handling.

Every upstream lookup requires a reverse reservation before dispatch. Stdout carries protocol frames only; arbitrary stderr is drained and discarded. The child receives only required platform environment values and the supplied Qloo key, never ADC, unrelated provider keys, HOME or arbitrary Node options. The docs MCP endpoint is reference tooling, never a runtime data source or credential destination.

The pinned harness ignores MCP cancellation notifications, so active cancellation/timeout reaps the child. Queue wait, replacement count, startup and shutdown are bounded; a cancelled waiter cannot terminate another caller. Six result envelopes normalize into typed port outcomes before any domain/browser consumer sees them.

## Credentials and evidence

The API resolves a configured Secret Manager version server-side with ADC. Production pins released numeric versions; local opt-in uses only the configured reference. No browser key, committed response capture or home-directory credential discovery is permitted. Image metadata remains unapproved until display rights are established; unverified explanation text is withheld.

The real curator uses request-specific Qloo evidence, while deterministic validation decides eligibility and winners. Missing or ambiguous identity must remain visible rather than guessed. [Architecture](../../docs/architecture.md) · [Source/capability/rights record](../../ai/qloo-capability-matrix.md) · [Current release evidence](../../infra/migration/production-release-execution-2026-10-28.md).

Install the locked runtime locally only when preparing a development environment:

```powershell
npm.cmd ci --prefix runtime/qloo --ignore-scripts --no-audit --no-fund
node --test runtime/qloo/typed-response.test.mjs
```
