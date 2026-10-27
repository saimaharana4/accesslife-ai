# Taste Duel local containers

The root Compose file now targets the separate Taste Duel project named
`taste-duel`. Its loopback ports
are 55436 (PostgreSQL), 18005 (API), and 13001 (web), so it does not attach to
the running AccessLife Compose project, the earlier Taste Duel foundation DB on
55435, or the AccessLife 5432/3000/8000 ports. The existing AccessLife
containers and volume retain their original project and are not managed by the
Taste Duel helper. PostgreSQL is a plain pinned PostgreSQL 16 image; this
product needs no PostGIS, pgvector, embedding model,
ingestion job, or background worker.

The committed `compose.tasteduel.env` contains nonsecret project/port settings.
The PowerShell entry point always passes it explicitly; it never loads a root
`.env` that may belong to another project. Default provider settings are off.
The database passwords in the Compose file are public, development-only values
for this loopback isolated stack. They must never be reused in GCP or any
shared environment. Production credentials remain Secret Manager references;
Qloo and Vertex access use server ADC.

Run from the repository root in PowerShell:

```powershell
# Check Docker Desktop, required nonsecret config and dedicated ports.
.\scripts\tasteduel-compose.ps1 preflight

# Build pinned, lockfile-based images. Compose waits for PostgreSQL and the one-shot migration before API/web.
.\scripts\tasteduel-compose.ps1 up

# Web app, API docs, and readiness.
# http://127.0.0.1:13001
# http://127.0.0.1:18005/docs
.\scripts\tasteduel-compose.ps1 health

# Re-run the one-shot migration command at any time.
.\scripts\tasteduel-compose.ps1 migrate

# Run generated web contract/state tests and the isolated API integration suite.
.\scripts\tasteduel-compose.ps1 test

# Create a synthetic completed game/challenge, restart only the Taste Duel API,
# then verify the saved result, invitation and fixed first replay round.
.\scripts\tasteduel-compose.ps1 persistence

# Inspect bounded service logs.
.\scripts\tasteduel-compose.ps1 logs

# Stop this Compose project; PostgreSQL data remains in taste-duel-data.
.\scripts\tasteduel-compose.ps1 down
```

`docker compose up --build` targets Taste Duel by default. The API waits until
the one-shot `migrate` service exits successfully before starting; the helper
adds the explicit project and nonsecret env file to that standard operation.
The standalone migration operation is `docker compose --project-name taste-duel
--env-file compose.tasteduel.env -f compose.yaml run --rm migrate`. Both use
the dedicated `tasteduel_migrator` role; API uses the
separate restricted `tasteduel_runtime` role. The API and Alembic accept only
the existing local foundation DB tuple on loopback port 55435/55436 or the exact
opt-in Compose tuple
(`database:5432/tasteduel_prompt5` with the expected role). The Compose API
image contains the pinned Qloo harness, tested Python runtime dependencies,
the Taste Duel migration lineage and Alembic configuration. It has no runtime
dependency download step. Web and API run as non-root; PostgreSQL uses its
official unprivileged process.

Optional live providers require ADC with Secret Manager access and Vertex IAM.
Set `TASTEDUEL_ADC_PATH` to the ADC JSON file and invoke
`.\scripts\tasteduel-compose.ps1 up -UseProviders`. The script checks only that
the file exists and mounts it read-only in the API container. It never reads or
copies the file. Qloo configuration supplies only the existing Secret Manager
resource name; the API resolves the key server-side. If ADC is missing, the
script warns and keeps both optional providers disabled. The provider overlay
is not a fixture mode and does not make a live provider call during preflight.

The default image is the real application shell with providers disabled; it
does not silently substitute generated rounds. The separate browser fixture
prototype can also run as a separate profiled development container:

```powershell
docker compose --project-name taste-duel --env-file compose.tasteduel.env -f compose.yaml --profile fixture up --build -d fixture-demo
# http://127.0.0.1:13002
```

That target sets `TASTEDUEL_FIXTURES=1`, runs Next development mode, and shows
the existing DEVELOPMENT FIXTURE labels. It has no API or database and stores
answers in memory. Its fixture modules are absent from the production web
bundle, which is separately checked in CI. Do not treat fixture output as Qloo
integration or as persisted API gameplay.

`docker compose down` is scoped to the explicit project and file and does not
remove `taste-duel-data`. The helper never issues `down -v`, `volume rm`, a
database reset, or an automatic cleanup. Deleting the named volume is a
separate destructive operation and permanently removes local game, challenge,
session and migration state. A container restart and image rebuild preserve
that volume.

The test action connects the isolated integration suite to the Compose DB at
loopback port 55436; it does not call the older helper that owns port 55435.
The persistence action uses the test-only `SyntheticCurator`, records one
short-lived guest token/slug and expected public first-round choices under the
ignored `.data/tasteduel-prompt14/` directory, restarts only this project's API,
then verifies via HTTP against the restarted API that the creator result and
invitation remain and a new guest starts the identical fixed first round. It
removes that token/slug artifact after the check; the retained report contains
only pass/fail facts. Qloo and Vertex remain disabled and are not contacted.

The current API does not yet expose a fixture-backed persisted game generator;
the database and API migration/readiness path can be verified locally while
full playable live flow remains dependent on genuine provider access and later
application gates. CI uses synthetic contracts and does not use event keys.
