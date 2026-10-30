# Named friend challenges

Source implementation and local verification; not a production deployment record.
The source schema head is `td0014`. The recorded public release remains `td0011`.

## Experience and privacy

“How may I call you?” and “Let’s go” create a named guest atomically. The nickname
labels a random session: duplicate names never merge users. Names are fixed for
the session. Existing unnamed sessions can be named without losing their games.

Complete a solo game, choose “Poke a friend”, then “Share the poke”. The button
carries the canonical URL. Native sharing runs directly from a click; cancellation
is neutral. Clipboard/manual selection cover unsupported browsers. Destinations
depend on the browser, device and installed apps.

A valid invitation says “{creatorName} poked you. Your move.” New visitors enter a
nickname before playing. Invalid/expired/revoked links are checked first. Self-play
is rejected. Each friend replays exactly the frozen five rounds, order and sides.

Reopening resumes the latest attempt; “Play these five again” explicitly starts
another. Every completed attempt retains its own score. The creator can page
through all friend outcomes, 20 at a time; friends see only their own attempts.
Verdicts handle either winner and ties. Known-answer replays are casual play,
not a measure of better taste. No sharing/comparison/replay calls Qloo or Vertex.

Names are escaped text: 1–24 normalized Unicode characters, without markup or
control characters. The creator name is public to invitation holders; recipient
names/scores are participant-only. Social metadata remains generic. Names never
enter analytics, URLs, browser storage or operational logs. Credentials remain
HttpOnly cookies. The 256-bit bootstrap retry key is credential material kept
only in memory. Losing the entire browser context cannot recover a guest without
its cookie.

## Lifecycle and physical cleanup

- Committed game actions, creating challenges, starting replays and discovery saves update
  activity. GETs, metadata and background polling never do.
- Unlinked sessions and unanswered invitations expire after one idle hour.
- A linked friend's activity protects the source data needed for their replay.
- After all started attempts finish, the challenge/results expire in ten minutes.
  Another attempt begun during that window returns it to active play.
- Hard session/evidence expiry and revocation always take precedence.
- A session supporting another retained game/challenge is preserved.
- Access fails immediately; deletion follows the next successful cleanup batch.
  Backlogs/failures can delay deletion; this is not an exact-time deletion SLA.

The opt-in `tasteduel-cleanup` Cloud Run job uses the pinned API image and existing
restricted migration identity: one task, one retry, 180 seconds, no providers.
A dedicated scheduler identity can invoke only this job, without overrides.
The UTC schedule is `*/10 * * * *`. New infrastructure defaults to disabled;
the schedule defaults to paused.

Each purge uses an advisory lock, bounded candidate IDs, 100 rows/table/pass,
three passes and a 25-second deadline that preserves completed work for commit.
The job runs at most three transactions, then inspects backlog. Active evidence,
dependencies and provider counters remain protected by DB policies/triggers.
Expired admission budgets and seven-day hash-only tombstones are also removed.
Logs contain aggregate counts/status, never names/tokens. Terraform defines
failure/backlog and 30-minute missing-completion console alerts. External
notification delivery is a separate unverified operator configuration.

SQL retains seven successful automatic backups, scheduled daily at 20:00 UTC.
This is a count limit: a backup can survive more than seven calendar days if
later backups fail. Live deletion does not rewrite backups/previews or
automatically shrink provisioned SQL disk. Existing versioned backup exports
delete archived object versions once their creation age reaches seven days; live export objects have no
automatic age limit. This feature creates no exports. Do not claim a universal
seven-day erasure deadline; any later export or restore needs its own retention
review and must reapply expiry before serving restored data.

## Local commands and evidence

Run from the repository root in PowerShell, using separate API/web terminals:

```powershell
uv run --project runtime/python --frozen python scripts/tasteduel_local.py migrate
uv run --project runtime/python --frozen python scripts/tasteduel_local.py api --api-port 8004
# In a second terminal:
corepack pnpm dev:live
# Web: http://127.0.0.1:3001; providers are disabled by default.
```

Stop API/web with Ctrl+C. Stop the isolated DB without removing its data:
`uv run --project runtime/python --frozen python scripts/tasteduel_local.py stop`.

The provider-free browser harness starts its own temporary API. Stop the normal
API on 8004 first, keeping the web preview running:

```powershell
$env:TASTEDUEL_TEST_WEB_URL = 'http://127.0.0.1:3001'
uv run --project runtime/python --frozen python scripts/tasteduel_challenges_browser_check.py
corepack pnpm test:challenges
```

The real local API/BFF/PostgreSQL/browser journey passed with three isolated
named sessions, two exact replays, shared verdicts, refresh recovery, clearing,
keyboard/reduced motion, eight full axe scans and zero provider/external requests.
Ignored artefacts: `.data/tasteduel-challenges/browser/`. These are synthetic
technical checks, not human playtests or proof of actual phone share targets.

## Reviewed rollout and rollback

The [October 29 cost refresh](../infra/migration/named-challenges-cost-review-2026-10-29.md)
prices six cleanup launches/hour, retries, polling, builds, logs and alerts at
US$95.38 under the user-approved US$100 ceiling. Existing US$90 billing alerts
remain conservative early warnings. Local validation is not an
authenticated cloud plan or cost approval. Do not reuse the same-schema hotfix
manifest or widen its guards. Preserve unrelated SQL, secrets and infrastructure.

1. Generate a compatibility source artifact with
   `uv run --project runtime/python --frozen python scripts/tasteduel_prepare_nickname_bridge.py`.
   It keeps the baseline UI/API shape, accepts optional new response fields,
   supports td0011–td0014, enforces installed lifecycle functions, and preserves
   the demo cutoff settings. The ignored artifact is not a commit/image/deployment.
2. Build/test and deploy the bridge first; record its immutable digests for rollback.
   Then migrate forward and deploy the feature. Do not roll back to the original
   API with its exact td0011 readiness check. No database downgrade is needed.
3. Use a new schema-changing release manifest, green exact-source CI, refreshed
   cost evidence and a reviewed full-root Terraform plan. Create cleanup paused.
   CI first exercises a populated td0011 upgrade and an injected transactional
   failure, proving existing attempts survive and security guards are restored.
4. Verify one real cleanup execution before resuming scheduling. Check two-device
   results, revocation/deletion, alerts and rollback. Actual iOS/Android share-sheet
   behaviour and notification delivery remain separate production/device checks.
5. The current horizon is 7 November 2026 at 10:15 IST. Admission closes at 08:15
   IST and new session hard expiry is capped at 09:45 IST, leaving time to drain
   active play. Verify final cleanup before the horizon.

After the final verified purge, the operator must pause and inspect the schedule:

```powershell
gcloud.cmd scheduler jobs pause tasteduel-cleanup --project project-bb13ecd8-9d67-408d-9a7 --location asia-south1
gcloud.cmd scheduler jobs describe tasteduel-cleanup --project project-bb13ecd8-9d67-408d-9a7 --location asia-south1 --format='value(state)'
```

Confirm `PAUSED` and disable the expected missing-heartbeat alert after the demo.
This is an explicit operational handoff: Cloud Scheduler is not listed among
services supporting resource-name IAM conditions, so the runtime receives no
project-wide scheduler administration to pause itself. The cleanup command
refuses DB work after the horizon; that alone does not stop execution charges.
[Supported IAM resource attributes](https://docs.cloud.google.com/iam/docs/conditions-resource-attributes).
Infrastructure retirement remains a separate reviewed action.
