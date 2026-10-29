# Second-Line 2.0: Financial Agent Assurance & Execution Platform

Synthetic cash-equity trade/position reconciliation for **one fictional bank**, built to answer a narrow question with evidence: *can an LLM agent work real operations tickets without being able to corrupt the books?*

An LLM agent investigates reconciliation breaks and **proposes** actions. Authenticated, deterministic code **authorizes, validates and commits** them. An independent **grader** scores the outcome against hidden ground truth, and hash-chained **receipts** plus replay make every step auditable.

Northeastern University · AAI 6665 · **Om Patel** and **Kunal Gupta** · MIT License

> **Status (M-0, PLANNED → building).** The platform skeleton is in place (Gradle services, Docker Compose profiles, DB roles, CI, contracts v1 in review). The ledger, gateway, agent and grader logic aren't built yet. Labels throughout: PLANNED · SCRIPTED · SIMULATED · REAL LLM RUN · EXPLORATORY · AMENDMENT · VERIFY. Nothing here is "certified" or production-grade; all data is synthetic.

---

## Contents
1. [How it works](#how-it-works)
2. [Repository layout](#repository-layout)
3. [Work split](#work-split)
4. [Prerequisites](#prerequisites)
5. [Quickstart](#quickstart)
6. [Configuration](#configuration)
7. [Commands](#commands)
8. [Testing and quality gates](#testing-and-quality-gates)
9. [Contributing: branches, PRs, merge rules](#contributing-branches-prs-merge-rules)
10. [Roadmap](#roadmap)
11. [Documentation map](#documentation-map)
12. [AI-assisted development](#ai-assisted-development)
13. [Data, safety and ethics](#data-safety-and-ethics)

---

## How it works

```text
 LLM agent (LangGraph)          proposes only: never writes the DB
        │  MCP tools (§10)
        ▼
 MCP adapter (Python)           thin, unprivileged, holds no credentials or policy
        │  run token (bound to one run + namespace)
        ▼
 Gateway (Java/Spring)          identity · schema · budgets · OPA policy → ALLOW / DENY / REVIEW_REQUIRED
        │                       REVIEW_REQUIRED → human maker-checker approval bound to the action digest
        ▼
 Ledger (Java/Spring + Postgres)   the ONLY component that mutates financial state:
        │                       pre-commit verifier re-checks evidence versions, balances, precision, policy;
        │                       journal + outbox row in one transaction; hash-chained decision receipt
        ▼
 Outbox → Kafka → Supervisor    async detective checks; can halt FUTURE actions, never undo commits
        │
 Grader (independent)           compares the final state with hidden truth the runtime can never read
```

The golden rules:
- **The trust boundary:** the LLM sits above the tool boundary; everything below it is deterministic and authenticated.
- **Money:** amounts are `NUMERIC`/`BigDecimal`/`Decimal` and decimal strings in JSON, never floats. A journal balanced per currency is *necessary, not sufficient*; the grader checks the economic outcome.
- **Truth isolation:** hidden truth (root causes, expected state deltas, canaries) lives only in privileged files that the agent, gateway, ledger, supervisor and console can't read. It's enforced by DB roles, the contract checker and CI.
- **Fail closed:** if identity, evidence version, state version, approval or policy can't be verified, nothing mutates and a typed error from `packages/contracts/errors.json` comes back.

Design decisions are ADRs in [`docs/adr/`](docs/adr/README.md). Key ones:
- [ADR-013](docs/adr/ADR-013-service-boundaries-mcp-adapter.md) service boundaries;
- [ADR-014](docs/adr/ADR-014-control-conditions.md) control conditions;
- [ADR-015](docs/adr/ADR-015-namespaces-truth-isolation.md) namespaces and truth isolation;
- [ADR-016](docs/adr/ADR-016-accounting-model.md) accounting model;
- ADR-017 evidence semantics.

## Repository layout

| path | what it is | owner | status |
|---|---|---|---|
| `services/ledger/` | Java 21 / Spring Boot financial authority (Postgres) | Om | skeleton (health + tests) |
| `services/gateway/` | Java policy enforcement point (identity, OPA, budgets) | Om | skeleton (health + tests) |
| `services/mcp-adapter/` | Python MCP tool surface (unprivileged) | Om | PLANNED (OM-06) |
| `libs/contracts-java/` | generated Java contract types, canonical JSON, digests | Om | PLANNED (OM-02) |
| `apps/console/` | Next.js review console (maker-checker approvals) | Om | PLANNED (OM-21) |
| `services/agent/` | LangGraph agent + deterministic rules baseline | Kunal | workspace scaffold (KG-01) |
| `services/supervisor/` | Kafka consumer: detective invariants, halts | Kunal | workspace scaffold (KG-01) |
| `packages/scenario-factory/` | causal synthetic world + hidden truth (**privileged**) | Kunal | PLANNED (KG-03) |
| `packages/evaluation/` | grader, experiment runner, statistics, replay (**privileged**) | Kunal | PLANNED (KG-06) |
| `packages/audit-verifier/` | independent receipt-chain verifier | Kunal | PLANNED (KG-12) |
| `packages/contracts/` | JSON Schemas, OpenAPI, `errors.json`, examples, `make contracts-check` | both | v1 in review (SH-02) |
| `infra/` | Docker Compose profiles, DB init (schemas + roles), observability, Toxiproxy, HPC | Om (hpc: Kunal) | core/app/events/obs/chaos working |
| `experiments/` | pre-registration, campaign configs, manifests, results | Kunal | PLANNED |
| `data/` | public reference snapshots, generated splits (gitignored), attack packs | Kunal | PLANNED |
| `tests/` | kit, security, infra (DB roles), cross-service integration, red-team | both | kit + infra suites working |
| `scripts/` | stdlib tooling: board, skills gate, contract check, CI change detection, rubric check | both | working |
| `docs/` | spec shards, ADRs, team boards and plans, setup guides, AI workflow (`docs/ai/`) | both | working |
| `.github/` | CI workflows, CODEOWNERS, repo settings as code (`settings.json`) | Om | working |

## Work split

The split follows the **tool boundary**. Om owns everything *below* it: the authority that decides and commits. Kunal owns everything *above* it: what acts, generates truth, measures and analyzes. Each side red-teams the other's.

### Om Patel: Authority & Platform + CI/CD
| area | path |
|---|---|
| Ledger: the only service that mutates financial state | `services/ledger/` |
| Gateway: identity, schema, budgets, OPA policy enforcement | `services/gateway/` |
| MCP adapter: unprivileged tool surface for the agent | `services/mcp-adapter/` |
| Generated Java contract types, canonical JSON (JCS), digests | `libs/contracts-java/` |
| OPA policies, budgets/halts, outbox → Kafka, receipts | `infra/opa/`, `services/ledger/`, `services/gateway/` |
| Secrets/redaction, observability, chaos/load testing, demo environment | `infra/` |
| Review API + review console | `apps/console/` |
| Agent-facing attack packs (held out from Kunal's agent tuning) | `data/attacks/` |
| CI/CD and repository settings; **the only person who merges**; Explorer HPC account | `.github/` |

### Kunal Gupta: Intelligence & Evidence
| area | path |
|---|---|
| Scenario factory + hidden truth (privileged) | `packages/scenario-factory/` |
| Public reference-data snapshots (GLEIF, ECB, Fed H.10, ISO codes) | `data/reference/` |
| Grader (independent oracle), experiment runner, statistics, replay, eval API | `packages/evaluation/` |
| LangGraph agent, prompts, model serving, rules baseline | `services/agent/` |
| Supervisor: Kafka consumer, detective invariants, halts | `services/supervisor/` |
| Independent receipt-chain audit verifier | `packages/audit-verifier/` |
| Platform red-team (attacks on Om's controls) | `tests/redteam/` |
| Pre-registration, pilot, campaigns, datasheet/model cards | `experiments/`, `docs/` |

### Shared (`SH-*` cards)
Contracts (`packages/contracts/`), domain ADRs, the end-to-end vertical slice, the report and the demo. Each shared card has one driver. Contract changes need a version bump, regenerated types and approval from both.

### Cross-checks (maker/checker)
- Every PR needs **the other person's** approval: Om approves Kunal's PRs and Kunal approves Om's. Nobody can approve a PR they pushed to last.
- Om attacks Kunal's agent with held-out attack packs and reviews the grader and monitor rules. Kunal red-teams Om's controls and verifies Om's receipts with independent code.

Task boards with every card, estimate and dependency: [`docs/team/OM.md`](docs/team/OM.md) · [`docs/team/KUNAL.md`](docs/team/KUNAL.md) · [`docs/team/SHARED.md`](docs/team/SHARED.md). Plan and milestone gates: [`docs/team/PLAN.md`](docs/team/PLAN.md).

## Prerequisites

| tool | version | needed for | check |
|---|---|---|---|
| Git | 2.40+ | everything | `git --version` |
| Docker Engine + Compose v2 | Compose **2.17+** (for `up --wait`) | running the stack | `docker compose version` |
| GNU Make | 3.81+ (macOS default) or 4.x | all commands | `make --version` |
| Python | **3.12** | tooling, contract check, Python services | `python3 --version` |
| uv | **0.13+** | Python workspace, contract check, pre-commit | `uv --version` |
| Java (Temurin) | **21**, only to run Java tests on the host; the Docker build needs no JDK | `make test`, `make test-ledger` | `java -version` |
| GitHub CLI | 2.x, logged in (`gh auth login`) | PR workflow, `make gh-check` | `gh auth status` |

Supported hosts:
- **Windows 11 + WSL2 Ubuntu 24.04** (keep the repo on the WSL disk, never `/mnt/c`): [`docs/setup/OM-windows-wsl.md`](docs/setup/OM-windows-wsl.md).
- **macOS on Apple Silicon:** [`docs/setup/KUNAL-macos.md`](docs/setup/KUNAL-macos.md).

Memory: the core profile needs about 0.8 GB and core+app about 2.3 GB; every profile at once needs about 4.4 GB. Images are multi-arch (amd64 + arm64).

## Quickstart

From a fresh clone. This exact sequence is what `make submission-check DEPLOY=1` and CI run.

```bash
git clone https://github.com/omunite215/Project_SecondLine.git
cd Project_SecondLine

make bootstrap            # once: checks Docker Compose ≥ 2.17, writes .env with random secrets (mode 600,
                          #       never overwritten), installs the pre-commit hook
make up PROFILES="core"   # Postgres 17, Redis 7, OPA; returns only when all are healthy (≤ 120 s cap)
make ps                   # service health
make test                 # Java unit tests + kit tests
make down                 # stop everything
```

Measured on 2026-10-28/29: `make up PROFILES="core"` was healthy in 8.4 s on both a Windows/WSL2 laptop and an Apple M4 Mac, and in 10.1 s in CI.

Start the Java services too with `make up PROFILES="core app"`. The first run builds the ledger and gateway images (about 80 s); after that they're healthy in seconds:
- ledger: `http://127.0.0.1:8081/actuator/health/readiness`
- gateway: `http://127.0.0.1:8080/actuator/health/readiness`

Database roles and truth isolation can be checked live with the core stack up: `python3 -m unittest discover -s tests/infra`.

## Configuration

- **Secrets:** `.env` (gitignored), generated by `make bootstrap` from [`.env.example`](.env.example). Every empty key gets a random secret: `POSTGRES_PASSWORD`, `LEDGER_SVC_PASSWORD`, `GRADER_SVC_PASSWORD`, `OPERATOR_SVC_PASSWORD`, `GRAFANA_ADMIN_PASSWORD`. Compose refuses to start without them (`${VAR:?}`), so there are no default passwords.
- **Profiles** (`infra/compose/docker-compose.yml`; host ports bind to `127.0.0.1` only):

| profile | services (ports) | memory |
|---|---|---|
| `core` | postgres :5432 · redis :6379 · opa :8181 | 768 MB |
| `app` | ledger :8081 · gateway :8080 | 768 MB each |
| `events` | kafka :9092 (KRaft) | 1 GB |
| `obs` | otel-collector :4317/:4318 · jaeger :16686 · prometheus :9090 · grafana :3000 | 256 MB each |
| `ui` | console (OM-21) | n/a |
| `chaos` | toxiproxy :8474 (postgres → :15432, redis → :16379) | 64 MB |

- **Database:** schemas `ledger` (owned by `ledger_app`), `audit` (the ledger may only INSERT + SELECT) and `eval` (hidden truth: only `grader_ro` reads it, never the ledger or the console's `operator` role). Login users `ledger_svc`, `grader_svc`, `operator_svc`. See `infra/db/init/`.
- **Pinned versions:** Spring Boot 3.5.16 and Java 21 (`gradle/libs.versions.toml`); Gradle 8.14.6 wrapper with sha256; Python locked in `uv.lock`; every container image and third-party GitHub Action is pinned to an exact version or commit.

## Commands

`make help` lists every target. A target that prints `TODO(<TASK>)` is planned; the named card builds it.

| command | what it does |
|---|---|
| `make bootstrap` · `make up PROFILES="…"` · `make down` · `make ps` · `make logs SVC=x TAIL=50` · `make db-shell` | run the local platform |
| `make test` · `make test-ledger` · `make test-gateway` | Java + kit test suites |
| `make lint` | pre-commit on every file (gitleaks, end-of-file, LF) |
| `make kit-check` | spec shards, boards, skills manifest, generated docs, kit/security tests, context budget (= CI `kit` job) |
| `make contracts-check` | validate every contract schema, example and OpenAPI file (SH-02) |
| `make submission-check [DEPLOY=1 REF=<branch>]` | course rubric check: organization, docs, quality, completeness, deployment |
| `make gh-check` · `make gh-apply` | live GitHub settings vs `.github/settings.json` (admin only) |
| `make board-next` · `python3 scripts/board.py show <ID>` | what to work on next |

## Testing and quality gates

| gate | where | what it proves |
|---|---|---|
| `kit` | CI (`kit-checks.yml`), `make kit-check` | boards and spec consistent; guardrail, integrity and contract tests pass; context budget |
| `changes` | CI (`ci.yml`) | decides which jobs a diff needs. It fails closed (unknown diff runs everything) and is required, so a failure can't skip checks |
| `lint` | CI, `make lint`, pre-commit hook | no secrets (gitleaks), clean line endings |
| `java` | CI | Gradle wrapper validated; all JUnit suites |
| `stack` | CI | bootstrap, core healthy, DB roles + truth-isolation tests (fail, never skip, in CI), every profile starts |
| `python` | CI (KG-01) | uv lock current, ruff + mypy, pytest, generated contract models up to date |

Every check above is a required status check on `main` (`.github/settings.json`). Tests are written first (TDD); test names carry their task ID (`test_OM_01_*`, `test_SH_02_*`).

## Contributing: branches, PRs, merge rules

- **Branches:** `<owner>/<TASK-ID>-slug`, e.g. `om/OM-01-bootstrap`, `kunal/KG-01-python-workspace`.
- **Commits:** start with the task ID and spec §, e.g. `OM-01 §7 §19: …`.
- **PR description:** follow `.github/pull_request_template.md`, with one evidence line per `done` criterion.
- **Reviews:** every PR needs the **other person's** approval, green and up-to-date CI, and every conversation resolved. The last pusher can't approve. Only Om merges (`gh pr merge <n> --squash --admin`); `main` has no bypass, so the rules apply to him too.
- **Behind `main`?** The PR **author** updates the branch; the reviewer never pushes to someone else's PR.
- **Contracts, ADRs, experiment changes:** `packages/contracts/` changes need a version bump and both approvals. Trust-boundary changes need an ADR first. Pre-registered hypotheses change only through a recorded AMENDMENT ([`docs/experiment-amendments.md`](docs/experiment-amendments.md)).
- **Full rules, rulesets and break-glass:** [`docs/setup/GITHUB.md`](docs/setup/GITHUB.md).

## Roadmap

| gate | exit evidence |
|---|---|
| **M-0** | shared ADRs accepted; contracts-v1.0.0 tagged; `make up PROFILES="core"` healthy on both machines; CI green |
| M-1 | dev split B1–B8 generates → loads → exports → grades; scripted oracle policy 100% correct; rules baseline graded |
| M-2 | a real LLM goes MCP → gateway → ledger on a B1 and a B7 case, graded and traced |
| M-3 | security tests pass; receipt chain verifies independently; the supervisor halts a scripted toxic sequence |
| M-4 | prereg frozen before any eval run; campaigns done; H1–H3 analyzed with confidence intervals; replay verified |
| M-5 | review console, chaos + load results, datasheet + model cards, demo from a clean clone, report |

Current card status: `make board-next`, or [`docs/team/TRACEABILITY.md`](docs/team/TRACEABILITY.md) for the requirement-to-card map.

## Documentation map

| doc | for |
|---|---|
| [`docs/spec/INDEX.md`](docs/spec/INDEX.md) | the specification, split into sections (intent, not evidence) |
| [`docs/adr/README.md`](docs/adr/README.md) | architecture decisions and the open-questions register |
| [`docs/domain.md`](docs/domain.md) | accounts, precision, posting patterns, break patterns B1–B8 |
| [`docs/team/PLAN.md`](docs/team/PLAN.md) | plan, milestone gates, collaboration protocol, calendar |
| [`docs/setup/`](docs/setup/) | machine setup (WSL2, macOS), GitHub/CI settings, Explorer HPC |
| [`docs/plans/`](docs/plans/) | implementation plans for larger cards |
| [`docs/experiment-amendments.md`](docs/experiment-amendments.md) | changes to the pre-registered design |
| [`packages/contracts/CLAUDE.md`](packages/contracts/CLAUDE.md) | contract layout and change flow |

## AI-assisted development

The team builds with Claude Code inside guardrails:
- a skills gate;
- hooks that block hidden-truth leakage;
- test-first plans;
- independent review agents.

The AI-facing files live in [`docs/ai/`](docs/ai/README.md). The root `CLAUDE.md` is a one-line import, because Claude Code only reads project memory from the root, and `.claude/` holds settings, hooks and skills. The product never depends on any of them.

## Data, safety and ethics

- **Synthetic only:** no real accounts, people, emails, settlement instructions or money. Public reference data (GLEIF, ECB, Fed H.10, ISO 20022 codes) is used only with its license and a content hash recorded.
- **Evaluation integrity:** eval and blind splits are never read or tuned on; prompts and thresholds come from the dev split only. H1–H3 are pre-registered, and changes are recorded as amendments.
- **Attack packs** (prompt injection, reward-hacking temptations) exist to test the controls; they ship with their mitigations.

## License

[MIT](LICENSE) © 2026 Om Patel and contributors.
