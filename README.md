# Taste Duel

[![Verification](https://github.com/saimaharana4/taste-duel/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/saimaharana4/taste-duel/actions/workflows/ci.yml)

**One favourite. Five duels. Can you predict Qloo’s cultural connections?**

[Play the web app](https://tasteduel-web-902056825143.asia-south1.run.app) · [How to play](docs/playing.md) · [Architecture](docs/architecture.md) · [Wiki](https://github.com/saimaharana4/taste-duel/wiki) · [MIT licence](LICENSE)

Choose a familiar music artist or film, predict which of two cultural entities Qloo ranked higher for that seed, reveal the answer, and save something worth exploring. Send a friend the exact same five comparisons with an independent score.

Your score measures prediction performance. It never becomes a judgement of your personal taste.

## Why Qloo matters

Qloo supplies request-specific cross-domain ranking evidence. A bounded Vertex AI curator chooses a supported candidate strategy and inspects deterministic pool feedback. Deterministic services retain authority over eligibility, winners, scoring and replay. An LLM can suggest plausible connections; it cannot establish the Qloo ordering frozen behind these answers.

Artist-to-film and film-to-artist paths have passed a small live technical matrix. Coverage varies by seed: finding a name does not guarantee ten eligible contestants or five valid rounds. Missing evidence produces an explicit unavailable or insufficient-coverage state rather than an invented answer.

## The experience

- Five rounds with accepted-answer reveals and an explicit Next action.
- Adaptive solo selection from the validated stored pool; no provider calls on answer or Next.
- Explicit discovery saves, separate from correct and incorrect predictions.
- Friend challenges with exactly the same delivered rounds, sides and order.
- Keyboard access, reduced motion, mobile layouts and original title-card artwork.
- Anonymous sessions with no account or forced sound.

## Run locally

Requires Docker Desktop. In PowerShell at the repository root:

```powershell
.\scripts\tasteduel-compose.ps1 preflight
.\scripts\tasteduel-compose.ps1 up
.\scripts\tasteduel-compose.ps1 health
# Web: http://127.0.0.1:13001
# API docs: http://127.0.0.1:18005/docs
.\scripts\tasteduel-compose.ps1 down
```

Stopping preserves the `taste-duel-data` volume. Default local startup disables external providers and reports that state honestly. A separately labelled fixture demo is available; genuine local play requires server-side ADC/Secret Manager configuration. See [local setup and operations](apps/api/CONTAINERS.md).

## Implementation and verification

The working source adds named guest entry, “Poke a friend”, participant-only
verdicts and inactivity/completion cleanup. This feature has local verification;
it is **not deployed**. See [behaviour, cleanup and rollout](docs/named-challenges.md).

Next.js App Router and TypeScript provide the web interface. FastAPI/Pydantic owns the API contracts, generated into frontend types. PostgreSQL 16 persists guest-owned games, immutable evidence, accepted answers and fixed challenges. GCP runs a public web service, an IAM-private API and one migration job on the existing dedicated SQL instance. No embedding model, ingestion pipeline or background worker is required.

The recorded release passed genuine Qloo/Vertex five-round play on its sealed production configuration, followed by unauthenticated public fixed replay and typed search. Checks cover response-loss recovery, isolated sessions, discovery persistence, keyboard/mobile/reduced-motion behavior, full axe scans and inspected answer/credential secrecy. Compatible revision recovery preserved stored history and enforced normal expiry. [Exact deployed identities and release evidence](infra/migration/production-release-execution-2026-10-28.md).

The 29 October hotfix is deployed from source `99c23fc`. It keeps a deterministically validated Qloo pool when the final curator response contains one of a small allowlisted set of model/tool mistakes, and otherwise returns a safe retry or coverage error. The original intermittent 503 cause was not captured, so this is a verified recovery-path fix rather than a claimed root-cause diagnosis. CI uses synthetic provider contracts, never event keys. [Hotfix evidence](infra/migration/production-hotfix-2026-10-29.md).

No structured, consent-based human playtest results have been recorded; discovery value remains unmeasured. Native screen-reader/zoom testing, managed Cloud SQL backup restore and notification-delivery rehearsal remain open. Original artwork and locally licensed fonts avoid unverified poster/photo reuse. [Validation boundaries](docs/verification.md) · [Asset licences](third_party/README.md).

## Explore the project

| Guide | Contents |
|---|---|
| [Documentation](docs/README.md) | Product, architecture, security and operations |
| [Playing](docs/playing.md) | Solo play, discoveries, challenges and expiry |
| [Architecture](docs/architecture.md) | Modules, curator and authoritative gameplay |
| [Security](docs/security.md) | API secrecy, isolation, provider limits and rights |
| [Operations](docs/operations.md) | Local runtime, deployment and recovery |
| [API](apps/api/README.md) | Implemented endpoints and generated contracts |
| [Verification](docs/verification.md) | Technical evidence and unresolved human checks |

The maintained `ai/` specifications and dated memory preserve the development record. Historical checkpoints are not current product status. Credentials, raw provider responses, state and local browser artifacts are excluded from source and container contexts.
