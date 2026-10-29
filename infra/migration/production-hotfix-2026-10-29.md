# Taste Duel production hotfix — 29 October 2026

The public application now serves source `99c23fc8824e8588af4e4c794e7683607e18e53c` from `tasteduel-web-hfs-99c23fc`; the IAM-private API serves `tasteduel-api-hfs-99c23fc`. Both receive 100% traffic with no revision tags or temporary candidate origins. Schema remains `td0011`; the migration job did not run.

The immutable image indexes are:

- API: `sha256:86351d5e904cfc37e8f8b9ab8cd5892a8fd774111001b6d3b6d9765676e7ea94`
- Web: `sha256:af8e8fff8e6a9d541c09def47992c3b2afa0f78211c6c06fb957af22025019ad`

[CI run 40843484745](https://github.com/saimaharana4/taste-duel/actions/runs/40843484745) passed for the exact source. A bounded candidate run used six Qloo requests and four Vertex requests: one genuine artist-to-film game completed five rounds with ten distinct contestants, persisted a discovery, recovered accepted answer/Next responses and replayed the same five comparisons in an isolated friend session. Eleven complete axe scans reported zero violations. Generation took 7.02 seconds in that sample; this is not a load or field-performance measurement.

The fix retains an already complete, deterministically validated Qloo pool only for a small allowlist of final model/tool-output mistakes. Authentication, deadline, budget, validator-veto and insufficient-coverage failures still fail closed. The original intermittent 503 cause was not logged, so this record does not claim a root-cause repair. Error categories and retry identity were validated with synthetic contracts rather than deliberately breaking live providers.

The candidate tag was intentionally public for testing and was not an access-control boundary. It was removed before promotion. Canonical and tagged direct API requests rejected unauthenticated access; after promotion the canonical API still returned 403 while the public web and same-origin readiness path returned 200. Secret versions remain pinned at version 1 and no secret payload was exported.

After promotion, a normal-refresh full-root Terraform plan reported 79 unchanged resources and zero mutations. The previous `r19p-e49564c` revisions remain available for compatible rollback. The carried cost review remains US$88.15 under the approved US$90 ceiling through 7 November 2026, 10:15 IST; this release did not perform a new billing observation.

The candidate challenge naturally expired before the later tokenless canonical replay. Production correctly rendered its unavailable-evidence state. The exact two-session replay had already passed against the identical candidate image digests, but this is not presented as a second post-promotion replay.

Human discovery value, native screen-reader/zoom testing, managed Cloud SQL backup restore and external alert delivery remain unverified. The historical initial release and recovery record remains [production-release-execution-2026-10-28.md](production-release-execution-2026-10-28.md).
