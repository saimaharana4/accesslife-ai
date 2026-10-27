# Taste Duel first-party event accounting

Implemented 27 October 2026. Server-private execution accounting is not human playtesting, preference inference, public popularity or a statistical impact claim. Rows are pseudonymous, not anonymous: short-lived internal session/game UUIDs support ownership and retry deduplication. No browser tracking library, analytics cookie, fingerprint, IP, raw query, entity title, guess correctness, score, ranking, model trace or provider payload is recorded here. No new person identity is introduced. No public report/telemetry API or live UI counters are provided.

## Events and denominators

Each fact is inserted in the same transaction as its successful authoritative mutation. Unique `(session_id,event,subject_id)` prevents retry/double-tap inflation. Five answers means five distinct accepted delivered rounds, not five browser clicks. Failed generation and merely preparing reservations are not game starts.

| Event | Meaning and deduplication unit |
| --- | --- |
| game_started | Committed ready solo game or committed fixed replay; one per game |
| game_completed | Fifth accepted answer and persisted result; one per game |
| round_answered | Accepted answer; one per delivered round, regardless of correct/incorrect |
| replay | New guest-owned fixed challenge game; one per replay game |
| challenge_create | Newly frozen share; one per challenge, not per retried creation |
| challenge_open | Qualified invitation acceptance that successfully creates a playable replay; one per replay game |
| challenge_complete | Fifth accepted answer in fixed replay; one per replay game |
| discovery_saved | Explicit new save; one per saved-discovery row. Unsave/re-save is a new action, not a new person |

`challenge_open` intentionally excludes landing-page GETs, social previews, browser prefetch and reload impressions. It does not measure everyone who viewed an invitation. `replay` and `challenge_open` describe the same successful start from different funnel perspectives and must not be added to infer users.

For eligible observed game cohorts, completion is distinct completed game IDs / distinct committed started game IDs; answer participation is accepted-round count / (5 × started-game count), with still-active games explicitly distinguished. Fixed-challenge completion is completed replay games / qualified challenge opens. Challenge creation is completed solo games that created a challenge / completed solo games. Discovery uptake is distinct started games with at least one explicit save / distinct started games; save-event totals alone are not unique people or preference predictions. These aggregate events cannot establish whether an item was interesting, surprising or culturally useful; ask consenting humans separately.

Do not divide independently truncated event totals to claim a valid cohort rate: match retained game IDs and start/completion observation windows, report N and incomplete exposure time, and exclude starts whose evidence aged out of the observation window. No rates are published automatically.

## Exclusions and limits

The server marks `source_mode=fixture` from its private curation receipt; this always remains separate from genuine Qloo execution. Deployment defaults to `cohort=excluded`. Only an operator explicitly setting `TASTEDUEL_EVENT_COHORT=operational` opts genuine runtime activity into operational reporting. Automated live probes, CI, local development and browser automation must leave the setting excluded; browsers cannot override it through an event body/header. Tests never claim to be human participants.

An operational flag does not prove humanness: automated traffic that plays a complete game can still enter operational counts. Existing session abuse controls reduce abuse but cannot identify all bots; operational aggregates must be described as game activity, never verified unique people. Consent-based playtest denominators are maintained separately and are not inferred from telemetry. For reports filter `source_mode=qloo`, `cohort=operational`, and unexpired records, then disclose this limitation.

## Retention and operations

Events expire seven days after creation, a first-party product policy rather than an invented Qloo licence term. They contain no Qloo content. Session clear immediately deletes that session's live accounting rows. Session/game physical deletion cascades. Per-owner opportunistic cleanup runs during event writes; report queries exclude expired records. Physical expiry for inactive sessions requires the privileged scheduled daily purge in the later production operations stage; this stage does not provision that job or claim it already runs. Backups follow separately documented backup retention and are not rewritten by session clear.

Local dedicated-database operator commands:

```powershell
uv run --project runtime/python --frozen python scripts/tasteduel_local.py events-report
uv run --project runtime/python --frozen python scripts/tasteduel_local.py events-purge
```

The report returns counts grouped only by event, source mode and cohort, excluding expired events, revoked/expired sessions and expired games. The purge deletes only expired events, never a database volume. Both commands scope-check the dedicated local container and cannot target the deployed AccessLife database. Before production telemetry opt-in, configure and verify daily privileged expiry cleanup and the backup policy; runtime has no cross-session report permission. Table RLS is forced; runtime can insert/select/delete its own events but cannot update facts or inspect another session. No UI claims are derived from these counters.
