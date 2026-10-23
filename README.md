# AccessLife AI

AccessLife AI is a planned accessible outing planner for wheelchair users, older adults and caregivers. It will check explicit mobility requirements before using Qloo cultural interests to rank suitable places, then explain the resulting itinerary with source evidence.

**Current status: documentation and repository foundation only.** There is no runnable application, deployed demo, provisioned AccessLife infrastructure or validated city coverage in this repository yet. A public repository alone does not make the project submission-ready.

## Planned experience

- Select **London, New York, Paris, Berlin or Chicago** and enter outing dates, mobility limits and interests.
- Discover places with separate entrance, toilet, lift and journey evidence; unknown information remains visible.
- Build and replan a local itinerary with rest breaks and per-leg/total walking or rolling limits.
- Combine local plans into a multi-city trip. Inter-city transfers remain user-arranged and unverified.
- Compare a baseline ranking against actual Qloo-informed rankings over the same eligible places.
- Complete the main flow without signing up, manipulating a map or enabling animation.

These are requirements, not claims of implemented behavior.

## Read the implementation documents

| Document | Purpose |
|---|---|
| [Product requirements](ai/prd.md) | Audience, MVP, future features and acceptance criteria |
| [Architecture](ai/Architecture.md) | Component contracts, data flow, APIs and managed GCP deployment |
| [Engineering rules](ai/rules.md) | Stack, boundaries, error handling, security and evidence policy |
| [Build phases](ai/phases.md) | Dependencies, component breakdowns and completion gates |
| [Design](ai/design.md) | Tokens, responsive screens, accessibility and component behavior |
| [Project memory](ai/memory.md) | Short dated record of completed work and blockers |

Read them in this order before implementation. The five-city and managed-services decisions supersede earlier one-city/single-VM proposals. Only the six maintained documents in `ai/` are published. The original local reference material in that folder stays unchanged and excluded from Git, and is not required to understand or reproduce these specifications.

## Planned stack and hosting

Next.js App Router, TypeScript, Tailwind, shadcn/React Aria, MapLibre and FastAPI/LangGraph; PostgreSQL 16 with PostGIS and pgvector; Vertex AI generation and CPU MiniLM embeddings. Managed GCP hosting will use Cloud Run, Cloud Tasks, a separate Cloud SQL instance, GCS and Secret Manager.

The incremental cloud target is **US$80 through judging**, excluding existing unrelated workloads. A regional cost estimate must pass before provisioning. This is a planning envelope, not a guaranteed bill or a hard GCP spending cap.

## Working with this repository now

```powershell
git clone https://github.com/saimaharana4/accesslife-ai.git
Set-Location accesslife-ai
Get-Content ai/prd.md
```

The [.env.example](.env.example) file contains placeholders for future configuration. Do not install dependencies, run migrations or deploy on the assumption that the application already exists. Executable setup, local URLs and shutdown instructions will be added when those components are implemented.

## Hackathon delivery

The target submission deadline is **31 October 2026 at 9:15 AM IST** (30 October at 11:45 PM EDT). The release must include a working external app, real Qloo integration, public runnable source and an open-source license. Retain live judging access through 5 November and required follow-up; published pages differ on the precise judging end time.

See the [official overview](https://qloo.devpost.com/), [rules](https://qloo.devpost.com/rules) and [schedule](https://qloo.devpost.com/details/dates). Requirements were reviewed on 24 October 2026; recheck before submission.

## License and data rights

Project source and documentation use the [MIT license](LICENSE). Third-party APIs, datasets, map tiles, venue images and excerpts retain their own terms. Do not infer permission to redistribute them from the project license. Source permissions and attribution must be recorded during the coverage phase.
