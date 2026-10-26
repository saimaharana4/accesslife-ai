# Taste Duel private Qloo MCP runtime

This runtime invokes the official canonical local-stdio MCP implementation in
`@qloo/qloo-harness@0.1.26`, with **Node 24.18.1**. `package-lock.json` pins the
complete package graph. It does not download packages during application startup.

**Prompt 8 update:** this file's Prompt 6 zero-call/no-HTTP statements below are
historical. An explicit `TASTEDUEL_QLOO_TRANSPORT=http_ranked` option now uses
reviewed GET Insights with explicit affinity ordering behind the same guard.
Separately opt into `TASTEDUEL_QLOO_HTTP_TYPED_SEARCH=true` to preserve raw
returned type evidence in GET search; it never silently replaces a failed MCP
workflow. Default MCP remains conservative and disabled unless configured.
The owned `typed-response.mjs` pre-harness shim preserves one unambiguous
artist/movie type from actual `types[]`, never the request scope; four offline
contracts pass, but two live canonical describe attempts still failed closed.
The successful grounded curator test used explicit HTTP search/ranking.
See [actual Prompt 8 evidence and limits](../../ai/prompt8-curator.md).

The parent now distinguishes persisted reservations from observed HTTP dispatch
notifications. Both paths share the same request budget and SQL key admission;
conservative reservations can exceed dispatches after a failed/cancelled send.

```powershell
npm.cmd ci --prefix runtime/qloo --ignore-scripts --no-audit --no-fund
```

The Python API owns one `ManagedMcpProcess` per instance and reuses it. The runner
injects the pinned package's `QlooClient` with one HTTP attempt, ten-second HTTP
deadline, two-MB body bound, event-host-only GETs and manual redirects. It uses
`createQlooTools({client})` rather than the CLI environment constructor, avoiding
home-directory credential/config discovery, persistent resolution caches and
filesystem observers. The pinned private chunk import is deliberate and must be
reviewed when upgrading the package.

Only `qloo_capabilities`, `qloo_describe` and `qloo_recommend` are callable. Startup
performs initialize/listTools/capabilities without Qloo network access, and checks
the package's exact discovered input schemas against `discovered-contract.json`
and contract checksum. That file contains public tool contracts, not API data or
an endpoint OpenAPI schema. It is not a source for generating browser contracts.
The snapshot must be present beside the runner; missing packaging fails startup.

Every actual upstream lookup, including UUID hydration, issues a reverse stdio
reservation request to the Python parent **before** dispatch. Without an installed
reservation callback every upstream request is denied. The parent applies the
generation's shared six-request/deadline allowance and persistent per-key controls;
one tool is not counted as one HTTP call. No automatic HTTP retry occurs here.
The Python process serializes workflows, bounds queue wait and kills/reaps the
child on an active timeout/cancellation because this harness version ignores MCP
cancellation notifications. A cancelled waiter cannot terminate another caller.
Per-call HTTP status metadata is snapshotted before releasing the workflow lock,
so a concurrent request cannot change authentication/rate-limit/error classification.
Authentication failures are terminal; rate limits and upstream 5xx failures remain
typed unavailable results rather than fabricated recommendations.

Stdout carries only newline-delimited MCP/reverse-reservation frames. Arbitrary
stderr is drained and discarded, never relayed or logged. The child receives only
PATH, SystemRoot, TEMP, TMP and the explicitly supplied Qloo key. It never gets
ADC, optional generation keys, HOME, inherited NODE_OPTIONS or an arbitrary host.
The documentation MCP endpoint is never used as a runtime source or credential
destination.

No raw-HTTP fallback is installed. The normalized private port preserves six
statuses, typed ambiguity choices, raw finite score values and input order. Image
URLs are unverified metadata only. Unreviewed explanation text is withheld. MCP's
compact affinity loses raw top-level/query precedence, and its default ordering
has not passed a live capability check; `ordering_verified` remains false. This
transport is implemented and synthetic-tested, **not** proof of a live ready game.
The Prompt 2 budget stays exhausted at 12/12; this iteration makes zero live calls.

## Enabling later, server-side only

Default `TASTEDUEL_QLOO_ENABLED=false` starts no child and reads no secret.
Opt-in API startup uses server ADC to access only this existing reference:
`projects/project-bb13ecd8-9d67-408d-9a7/secrets/accesslife-qloo-api-key/versions/latest`.
The legacy secret name is preserved; this stage creates/renames no secret or IAM
resource. The SDK can read ADC configuration; the MCP child receives no ADC.
Startup secret resolution and MCP initialization are independently bounded by
five seconds each by default. No payload lookup was exercised in this stage.

The API lifespan constructs one guarded port/child and closes it on shutdown.
Callers must use `async with port.request_budget(...)` around the entire intended
generation: hard ceiling six upstream requests and twenty seconds across tools,
hydration, retry and audit work. There is at most one eligible retry per workflow;
the total generation budget still wins. Authentication/contract failures never
retry or switch providers. A failed reservation remains consumed conservatively.
Per-call default deadline is twelve seconds including queue wait; active timeout
reaps the process. Restart allowance is two replacements per API lifespan.

Additive local migration `td0005` stores key fingerprints/counters only under
forced RLS. Defaults: thirty requests/minute, minimum 200 ms between dispatches,
three eligible transient failures open the circuit for thirty seconds, and
authentication failure blocks that fingerprint until credential rotation or a
reviewed operator repair. The lower persisted per-key minute limit wins across
configuration changes. These values are engineering safeguards, not provider
quota/expiry metadata. Every participating instance must share this PostgreSQL
store; a legacy runtime bypassing it must be separately coordinated before live
use. Database failure denies dispatch rather than falling back to a local bucket.

The new isolated container is `infra/containers/tasteduel-api.Dockerfile`;
`runtime/python/uv.lock` pins its minimal Python environment without old map,
embedding/ingestion or planner dependencies. Both base images and uv are digest
pinned. It is tested with networking disabled, read-only filesystem and UID10001.
Legacy Compose/cloud workflows still reference their original images; this file
does not provision, deploy or cut over a service.

Remaining probes, under a **new separately recorded budget**, are typed canonical
describe-to-resolved-ID recommend for both cross-domain directions, actual
canonical Insights order/type preservation and raw-versus-compact score
precedence, followed by same-domain coverage if needed. Internal hydration must
count too; no exact one-request maximum is assumed. Books/persons, nested
explanation support and broad named-seed coverage remain gated. API enablement,
synthetic contract success and a container build cannot replace these checks.

Sources: [pinned package](https://registry.npmjs.org/@qloo/qloo-harness/0.1.26),
[capability and rights record](../../ai/qloo-capability-matrix.md). Harness MIT
licensing does not grant rights to provider data or linked images.
