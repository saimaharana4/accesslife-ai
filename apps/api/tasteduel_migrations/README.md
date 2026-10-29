# Taste Duel database migrations

This immutable Alembic lineage owns the `tasteduel` schema. The current head is `td0011`. Local Compose uses the dedicated `tasteduel_local` database; GCP uses a separate Taste Duel logical database on the retained dedicated SQL instance. The old AccessLife logical database and migration history are not migration targets.

Use the maintained entry point from the repository root:

```powershell
.\scripts\tasteduel-compose.ps1 migrate
```

The migration principal owns schema changes and the immutable revision stamp. The restricted runtime principal receives explicit DML/stamp privileges, not schema DDL, superuser or RLS-bypass access. Owned tables use forced RLS with an authenticated transaction-local owner context. That context is a trusted application boundary, not a cryptographic database identity; possession of a database password still requires protection.

| Revisions | Responsibility |
|---|---|
| `td0001`–`td0004` | Initial storage, immutable delivery/ownership guards and checked mutation receipts |
| `td0005` | Shared per-key provider admission controls |
| `td0006` | Durable generation claims/private receipts and authoritative gameplay |
| `td0007` | Versioned adaptive solo selection and discoveries |
| `td0008` | Exact delivered-round challenges and fixed replay |
| `td0009` | Private usage/abuse accounting |
| `td0010` | First-party event accounting |
| `td0011` | Restricted bounded expiry operations and hash-only expired-link tombstones |

Applied migrations are not edited to change behavior. Add forward migrations, preserve rollback-compatible data and never delete a volume to make startup pass. Physical expiry cleanup uses a fixed reviewed migration-role operation and remains manual; evidence expiry is enforced on access independently. Private storage does not grant new provider retention rights.

[Local runtime](../CONTAINERS.md) · [Current deployment/recovery](../../../infra/migration/production-release-execution-2026-10-28.md)
