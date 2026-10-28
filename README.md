# Project_SecondLine

**Second-Line 2.0 — Financial Agent Assurance & Execution Platform** (Northeastern AAI 6665 · Om Patel + Kunal Gupta).

Synthetic cash-equity trade/position reconciliation for one fictional bank. An LLM agent proposes actions; authenticated deterministic code authorizes, validates and commits them; an independent oracle grades outcomes against hidden truth; receipts and replay make every step auditable.

> Status: **PLANNED**. The repo currently holds the spec, task boards and Claude Code kit; no product code yet. See [START_HERE.md](START_HERE.md).

## Work split

The split follows the **tool boundary**: Om owns everything *below* it (the authority that decides and commits), Kunal owns everything *above* it (what acts, generates truth, measures and analyzes).

### Om Patel: Authority & Platform (below the tool boundary) + CI/CD

| Area | Path |
|---|---|
| Ledger: the only service that mutates financial state (Java/Spring + Postgres) | `services/ledger/` |
| Gateway: identity, schema, budgets, OPA policy enforcement | `services/gateway/` |
| MCP adapter: unprivileged tool surface for the agent | `services/mcp-adapter/` |
| Generated Java contract types, canonical JSON, digests | `libs/contracts-java/` |
| OPA policies, budgets/halts, outbox → Kafka, receipts | `services/`, `infra/opa/` |
| Secrets/redaction, observability, chaos/load testing | `infra/` |
| Review API, review console, demo environment | `apps/console/` |
| Agent-facing attack packs (held out from Kunal) | `data/attacks/` |
| CI/CD, repo settings; **the only one who merges**; approves Kunal's PRs; Explorer HPC account | `.github/` |

### Kunal Gupta: Intelligence & Evidence (above the tool boundary)

| Area | Path |
|---|---|
| Scenario factory + hidden truth (privileged) | `packages/scenario-factory/` |
| Public reference-data snapshots (GLEIF, ECB, Fed H.10, ISO codes) | `data/reference/` |
| Grader (independent oracle), experiment runner, statistics, replay, eval API (privileged) | `packages/evaluation/` |
| LangGraph agent, prompts, model serving, rules baseline | `services/agent/` |
| Supervisor: Kafka consumer, detective invariants, halts | `services/supervisor/` |
| Independent receipt-chain audit verifier | `packages/audit-verifier/` |
| Platform red-team (attacks on Om's controls) | `tests/redteam/` |
| Pre-registration, pilot, campaigns, datasheet/model cards | `experiments/`, `docs/` |
| **Opens PRs for Om's approval; never merges or pushes to `main`** | |

### Shared (`SH-*` cards)

Contracts (`packages/contracts/`), domain ADRs, the end-to-end vertical slice, the report and the demo. Each shared card has one driver; contract changes need a version bump, `make codegen` and approval from both.

### Cross-checks

- Om attacks Kunal's agent with held-out attack packs and reviews the grader and monitor rules.
- Kunal red-teams Om's controls and verifies Om's receipts with independent code.
- Om's own boundary PRs get Kunal as reviewer.

## Where the details live

- Task boards: [docs/team/OM.md](docs/team/OM.md) · [docs/team/KUNAL.md](docs/team/KUNAL.md) · [docs/team/SHARED.md](docs/team/SHARED.md)
- Plan and milestone gates: [docs/team/PLAN.md](docs/team/PLAN.md)
- Decisions: [docs/adr/README.md](docs/adr/README.md)
- Spec (read one shard at a time): [docs/spec/INDEX.md](docs/spec/INDEX.md)

## Workflow

`/next-task` → build test-first → `/finish-task` → `/open-pr` → Om reviews (`/review-pr <n>`) and merges.
