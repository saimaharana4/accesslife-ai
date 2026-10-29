# Taste Duel infrastructure

The deployed topology is public `tasteduel-web`, IAM-private `tasteduel-api`, one restricted migration job and the `tasteduel` logical PostgreSQL database on the retained dedicated SQL instance. It needs no ingestion worker, embedding model, queue, second SQL instance or separate environment projects.

The [release execution record](migration/production-release-execution-2026-10-28.md) owns verified deployed source/image/schema/secret identities and measured boundaries. [Release/recovery tooling](terraform/RELEASE.md) describes immutable images, reviewed full-root saved plans, controlled candidates, public cutover, compatible revision recovery and bounded manual maintenance. Source fixes awaiting publication are not assumed deployed.

## Identity and preservation

- Web invokes the private API with IAM and has no database/Qloo secret access.
- API runtime and migration job have separate database principals and narrowly scoped Secret Manager references; Vertex uses IAM.
- GitHub uses restricted numeric repository/owner identity and main/environment constraints through keyless WIF.
- Existing SQL instance, state bucket/prefix, registry and shared immutable-name secrets are retained intentionally. Old AccessLife data/source recovery remains separate.
- Complete plans must preserve unrelated resources and explicit old database/user ownership. No routine targeting conceals a partial plan.

The obsolete AccessLife runtime was retired earlier with explicit authorization. Broader final retirement is a separately reviewed action, not a branding rename or startup step.

## Monitoring and evidence

Three-region canonical readiness monitoring, an enabled console alert, sanitized dashboard and exact two-service request-URL exclusion are installed. The observed sample passed 18/18 uptime points across three locations. No external notification recipient/delivery rehearsal is claimed; historical logs age out under their existing policy.

Compatible rollback/return preserved 14 inspected history-table hashes and provider counters with normal expiry. It did not replay an expired game. The earlier recovery test was a scoped logical restore, not a managed Cloud SQL backup restore.

The [carried-forward 28 October forecast](migration/production-cost-review-2026-10-28.md) is US$88.15 under the user-approved US$90 envelope through 7 November 2026 10:15 IST, retaining seven backups. This is not a new billing refresh or spending cap. Alerts are notifications.

## Local static validation

```powershell
uv run --project runtime/python --frozen python scripts/tasteduel_infra_validate.py
```

Static validation is not a deployment, restore, IAM connectivity or public gameplay test. Dated inventory/foundation/candidate records under `migration/` preserve their original checkpoints; current execution supersedes old active-status statements.
