# Running and releasing Taste Duel

Use the [container guide](../apps/api/CONTAINERS.md) for exact PowerShell commands, optional ADC mounting and the labelled fixture demo. Standard startup contains web, API, PostgreSQL and a one-shot migration. Default mode disables external providers rather than fabricating live rounds.

Stopping preserves the database volume. Deleting a volume is a separate destructive operation, never a startup repair. Development-only local values must not be reused in shared deployments.

## Production

The canonical app uses [its actual Cloud Run URL](https://tasteduel-web-902056825143.asia-south1.run.app); no purchased domain is claimed. The API is IAM-private; web uses its canonical URI as the token audience. Cookies are host scoped, mutation origins exact and temporary candidate tags/origins removed before public release.

Build from a committed successful-CI source archive and publish immutable digests. Independently review migrations and full-root saved Terraform plans. Test controlled candidates before explicit promotion. A zero-percent tag remains reachable and is not a security boundary; new services start with real allocation under the reviewed IAM boundary.

[Release/recovery tooling](../infra/terraform/RELEASE.md) and [execution evidence](../infra/migration/production-release-execution-2026-10-28.md) record exact source, digests, schema and secret versions. A local patch or successful build does not establish deployment. Generation-failure/retry changes remain release work until that record verifies their publication.

## Monitoring and recovery

Readiness checks database/schema and admission without invoking providers. The installed three-region check runs every 900 seconds. A dashboard shows request metrics and sanitized events; an enabled policy creates console incidents. No external recipient or notification-delivery rehearsal is claimed.

Expiry access fails closed before physical purge. Use only the fixed reviewed `purge-expired` operation, inspect backlog and preserve active evidence. Cleanup is bounded manual maintenance, not a recurring scheduler or guaranteed SLA. Backups retain their separate policy.

The completed compatible revision rollback/return preserved history hashes and provider counters. Its game had expired: this proves health, expiry and historical-data preservation, not active replay during rollback. The earlier restore was a scoped in-memory logical restore, not a managed Cloud SQL backup restore or durable full export. Never restore over the live database for a rehearsal.

The carried-forward 28 October forecast was US$88.15 under the approved US$90 envelope through 7 November 2026 10:15 IST, preserving seven backups. This is not a new billing observation or a spending cap. Infrastructure retirement requires a separate reviewed scope and is not performed by local startup commands.
