<p align="center">
  <img src="src/guide/assets/hero.png" alt="Taste Duel — One favourite. Five duels. Cultural discovery powered by Qloo." width="100%" />
</p>

<h1 align="center">Taste Duel</h1>
<p align="center"><strong>One favourite. Five duels. Your move.</strong></p>
<p align="center">
  <a href="https://tasteduel-web-902056825143.asia-south1.run.app"><strong>Play Taste Duel ↗</strong></a> ·
  <a href="src/guide/playing.md">How to play</a> ·
  <a href="src/guide/architecture.md">Architecture</a> ·
  <a href="src/guide/README.md">Documentation</a>
</p>
<p align="center">
  <a href="https://github.com/saimaharana4/taste-duel/actions/workflows/ci.yml"><img src="https://github.com/saimaharana4/taste-duel/actions/workflows/ci.yml/badge.svg?branch=main" alt="Taste Duel verification" /></a>
  <img src="https://img.shields.io/badge/Cultural_intelligence-Qloo-b8a0ff" alt="Qloo cultural intelligence" />
  <img src="https://img.shields.io/badge/Curated_with-Vertex_AI-dfff4f" alt="Curated with Vertex AI" />
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-white" alt="MIT licence" /></a>
</p>

Start with a music artist or film you love. Taste Duel builds five two-choice cultural matchups around it. For each one, guess which contender Qloo ranks higher, reveal the connection, and save anything that deserves a closer look. Then hand your exact five rounds to a friend. Their confidence can take its own chances.

**Qloo brings the ranking evidence. You bring the predictions. The score judges your guesses, not your taste.**

<p align="center">
  <img src="src/guide/assets/duel-flow.svg" alt="Pick a favourite, make five predictions, see Qloo's accepted ranking, then challenge a friend to the same rounds." width="100%" />
</p>

## Five rounds. A few new favourites.

|                        | Your move                                                                                                      |
| ---------------------- | -------------------------------------------------------------------------------------------------------------- |
| **Say hello**          | Choose a nickname for this guest session. Friends can see it on invitations and results.                       |
| **Pick a favourite**   | Search for a music artist or film and choose a supported cross-domain journey.                                 |
| **Make the call**      | Predict the higher-ranked contender, reveal the accepted answer, then continue.                                |
| **Keep the discovery** | Save a contender you want to explore. Saves are your choice, separate from correct answers.                    |
| **Poke a friend**      | Share an invitation to the exact same five rounds. Compare independent scores and a lightly sarcastic verdict. |

Friend challenges freeze the actual round order and sides; your friend gets independent answers and a separate score. Both players can return to the shared verdict while their sessions and challenge remain valid. If your friend wins, congratulations: you supplied the receipts for their group-chat speech. Sharing uses native sharing where available, with clipboard and manual-copy fallbacks.

## Cultural discovery with evidence

**Qloo supplies the ranking. Vertex AI curates the journey. The server owns the score.**

Qloo provides request-specific cultural ranking evidence across music and film. A bounded Vertex AI curator proposes a supported strategy; deterministic validation checks the candidate pool before any round is delivered. An LLM cannot invent the answers or change a completed game.

Coverage varies by seed. When there is not enough evidence for five valid rounds, Taste Duel explains the limitation. Answering, saving, sharing, replaying and comparing scores do not trigger additional Qloo or model calls.

```mermaid
flowchart LR
    Browser["Next.js browser"] --> BFF["Same-origin gateway"]
    BFF --> API["IAM-private FastAPI"]
    API --> DB[("PostgreSQL · isolated guest state")]
    API --> Curator["Bounded Vertex AI curator"]
    Curator --> Qloo["Typed Qloo tools"]
    Curator --> Validator["Deterministic pool validation"]
    Validator --> DB
```

## Built for a proper duel

- **Authoritative gameplay:** five rounds, accepted-answer recovery and server-calculated scores.
- **A fair rematch:** frozen challenge replay with independent answers and scores.
- **Guest privacy:** no account required; nicknames are labels, not login identities. Secure cookies identify sessions.
- **Designed to play:** keyboard controls, reduced motion, responsive layouts, original title cards and locally hosted fonts.
- **Short-lived state:** inactivity expiry blocks access immediately. Recurring bounded cleanup removes expired records; backups follow a separate retention policy.

[Gameplay details](src/guide/playing.md) · [Friend challenges and retention](src/guide/named-challenges.md) · [Security and privacy](src/guide/security.md)

## Run locally

Requires Docker Desktop. From the repository root in PowerShell:

```powershell
.\scripts\tasteduel-compose.ps1 preflight
.\scripts\tasteduel-compose.ps1 up
.\scripts\tasteduel-compose.ps1 health
```

Open [the web app](http://127.0.0.1:13001) or [API documentation](http://127.0.0.1:18005/docs).

Default startup disables external providers and reports that state honestly. Use the [container guide](apps/api/CONTAINERS.md) for the labelled fixture demo or genuine provider configuration.

```powershell
.\scripts\tasteduel-compose.ps1 down
```

Stopping preserves the local database volume.

## Repository map

```text
apps/
  api/                 FastAPI, domain rules, provider adapters and migrations
  web/                 Next.js interface and same-origin API gateway
packages/contracts/    Exported OpenAPI and generated wire contracts
runtime/               Locked Python and Qloo runtime dependencies
infra/
  containers/          Production image definitions
  local/               Local Compose stack and nonsecret settings
  terraform/           Cloud resources, IAM and monitoring
  releases/            Immutable release manifests
  migration/           Dated deployment and preservation evidence
quality/                API, database and browser checks; test and lint policy
scripts/                Development, verification and release tooling
src/
  guide/                Product guides, artwork and operational documentation
  attribution/          Font and artwork notices
```

**Stack:** Next.js · React · TypeScript · FastAPI · PostgreSQL · Qloo · Vertex AI · Cloud Run · Terraform.

## Explore further

| Guide                                     | What you will find                                            |
| ----------------------------------------- | ------------------------------------------------------------- |
| [How to play](src/guide/playing.md)       | Predictions, reveals, discoveries and friend challenges       |
| [Architecture](src/guide/architecture.md) | Provider boundaries, contracts and authoritative transactions |
| [Operations](src/guide/operations.md)     | Local setup, production releases, monitoring and recovery     |
| [Verification](src/guide/verification.md) | Recorded checks and the limits of the evidence                |
| [Security](src/guide/security.md)         | Private answers, session isolation and secret handling        |

Automated checks cover database isolation, response-loss recovery, exact replay, keyboard and mobile layouts, privacy and accessibility scans. These checks do not replace native-device sharing, screen-reader testing or human feedback; see the verification guide for current boundaries.

## Licence

Source is [MIT licensed](LICENSE). Fonts and artwork retain their [separate notices](src/attribution/README.md).
