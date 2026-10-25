# Second-Line 2.0 — Claude Code project memory
<!-- Maintainers: keep this file < 150 lines. Area detail belongs in nested CLAUDE.md files, .claude/rules/ or a skill.
     HTML comments are stripped before Claude reads the file (zero tokens). Check the always-loaded cost with `make ctx`. -->

Synthetic cash-equity trade/position reconciliation for ONE fictional bank (Northeastern AAI 6665 — Om Patel + Kunal Gupta; repo github.com/omunite215/Project_SecondLine). An LLM agent proposes actions; authenticated deterministic code authorizes, validates and commits them; an independent oracle grades against hidden truth; receipts and replay make every step auditable.
**Reality check:** `docs/spec/` is intent, not evidence. Status = what code, passing tests and measured artifacts show. Never call anything done, measured or working without executable evidence.

## Who is who
- Your human is named in `CLAUDE.local.md` (`owner:`, machine limits, `learn_mode`). Default to their board.
- **Om — Authority & Platform (below the tool boundary) + CI/CD owner:** ledger, gateway, MCP adapter, OPA, budgets/halts, outbox→Kafka, receipts, secrets/redaction, observability, chaos/load, review API, console, demo env, agent-facing attack packs. Approves and merges every PR; holds the Explorer HPC account.
- **Kunal — Intelligence & Evidence (above it):** scenario factory + truth, reference data, grader, rules baseline, LangGraph agent, prompts, model serving, supervisor, audit verifier, platform red-team, runner, prereg, pilot, campaigns, stats, replay, eval API, datasheet/model cards. Opens PRs for Om's approval; never merges or pushes to main.
- Shared `SH-*`: contracts, domain ADRs, vertical slice, report, demo. If a change touches the other person's area, keep it minimal and flag it in the PR.
- Boards `docs/team/{OM,KUNAL,SHARED}.md` · plan + gates `docs/team/PLAN.md` · decisions `docs/adr/README.md` · skills `docs/team/SKILLS.md`.

## Skills gate (hard requirement)
- Required plugins/skills per person live in `tooling/claude-skills.json`. The human installs them in their own terminal (`make skills-install`); `make skills-check` verifies.
- While the session line says `[skills] RED`: don't plan or edit; give the human the printed fix commands. Hooks block project edits and non-setup shell commands, and `board.py set <ID> doing` refuses. Never work around the gate or touch `.claude/.skills-ok.json`.

## Golden rules
1. LLMs propose → gateway (identity, schema, budgets, OPA) authorizes → ledger pre-commit verifier validates → only the ledger mutates financial state → independent grader scores → the async supervisor may halt FUTURE actions, never undo commits.
2. Synthetic only: no real accounts, PII, emails, settlement instructions or money. Public reference data only with license + hash recorded.
3. Money, quantity, price, FX: BigDecimal / NUMERIC / Decimal (strings in JSON). Never float. Balanced per currency is necessary, not sufficient.
4. Hidden truth (Truth docs, `truth_ref`, `SLCANARY-` canaries, root-cause labels) never reaches agent, MCP adapter, gateway, ledger, supervisor, console, prompts or traces.
5. Never read or tune on eval/blind data (deny-listed). Prompts, few-shots and monitor thresholds come from the dev split only.
6. H1–H3 are pre-registered: no silent changes. Use `/amend`; label exploratory work.
7. Fail closed: if identity, evidence version, state version, approval or policy can't be verified → no mutation + a typed error from `packages/contracts/errors.json`.
8. Cross-service shapes live only in `packages/contracts/` (version bump + `make codegen` + `/handoff` + both approve).
9. Trust-boundary or architecture change → ADR first (`/adr`).
10. Prose uses status labels: PLANNED · POC-REPORTED · SCRIPTED · SIMULATED · REAL LLM RUN · EXPLORATORY · AMENDMENT · VERIFY. Never "certified", "bank-safe", "regulator-approved".
11. Traceability: task ID + spec § + REQ-/T- IDs in branch, commit, PR and test names.
12. Credentials never pass through you: no passwords, Duo codes, tokens or keys. HPC and GitHub use the human's own sessions (`make hpc-*`, `gh`).

## Using the skills (details: docs/team/SKILLS.md)
- superpowers: `test-driven-development` for every code change (failing test first); `systematic-debugging` before changing code for any failure; `verification-before-completion` before claiming done/passing and before `/finish-task`; cards ≥2d → `writing-plans` into `docs/plans/<ID>.md`, then `executing-plans` across sessions (read the plan instead of re-planning); `requesting-code-review` before `/open-pr`.
- The card + its § shards are the approved design: `brainstorming` only when a card leaves a design decision open. These instructions override skill defaults. No git worktrees on Om's 16 GB laptop.
- LSP plugins: read diagnostics after edits instead of running full builds to find type errors.
- A card's `skills:` line is mandatory for that card (mcp-server-dev on OM-06, frontend-design on OM-21/22, insecure-defaults on security cards, LangGraph skills in services/agent, document-skills for SH-15/16).

## Repo map
```text
apps/console/              Next.js review console                        Om
services/ledger/           Java/Spring financial authority (Postgres)    Om
services/gateway/          Java/Spring policy enforcement point          Om
services/mcp-adapter/      Python MCP tool surface, unprivileged         Om
libs/contracts-java/       generated Java types, JCS, digests            Om
services/agent/            LangGraph agent + rules baseline              Kunal
services/supervisor/       Kafka consumer, detective invariants, halts   Kunal
packages/scenario-factory/ causal world + hidden truth   (PRIVILEGED)    Kunal
packages/evaluation/       grader, runner, stats, replay (PRIVILEGED)    Kunal
packages/audit-verifier/   independent receipt-chain verifier            Kunal
packages/contracts/        JSON Schemas, OpenAPI, errors, test vectors   both
infra/                     compose, db init, opa, observability, toxiproxy, k6, hpc
experiments/               prereg (frozen/), configs, manifests, results; runs/ raw (gitignored)
data/                      reference/ snapshots · generated/{dev,eval,blind}/ · attacks/{dev,eval}/
tooling/                   claude-skills.json (skills gate manifest) + skills.lock.json
tests/                     cross-service integration, security, redteam, chaos, e2e
docs/                      spec shards, team boards, ADRs, setup guides, plans, report
scripts/                   board.py, skills.py, ctx.py, hpc.sh, split_spec.py, ctx_budget.py
```

## Commands
A target that prints `TODO(<TASK>)` is not built yet — that task builds it. Test targets are quiet by design.
```text
make help · make kit-check · make board-next · make trace · make skills-check|skills-list
make up PROFILES="core app"      (profiles: core app events obs ui chaos) · make down · make logs SVC=x TAIL=50
make codegen · make contracts-check
make test-ledger|test-gateway|test-mcp|test-policy|test-py|test-agent|test-factory|test-eval|test-supervisor|test-console
make test-int|test-sec|test-redteam|test-chaos|test-load|leakage-check
make factory SPLIT=dev N=40 · make run-one SCN=<id> CONTROLS=off|monitor|full STRATEGY=llm|rules
make pilot · make campaign CFG=<yaml> SHARD=1/2 · make analyze CAMPAIGN=<id> · make replay RUN=<id> MODE=action|live
make hpc-check|hpc-status|hpc-tunnel|hpc-health|hpc-logs (hpc-up/hpc-down ask first) · make demo-up|demo-seed|demo-run|demo-test
python3 scripts/board.py next | show <ID> | set <ID> doing|review|done --evidence "<tests/artifacts>"
```

## Spec lookups (cheap)
- Never open `docs/spec/MASTER_SPEC.md` (~24k tokens). Read `docs/spec/INDEX.md`, then ONE shard in `docs/spec/sections/`.
- Questions spanning several sections → the `spec-scout` subagent. Task cards list the § to read; start there.

## Working loop
1. `/next-task` → the gate line must be GREEN → read only what the card lists → plan (≤10 lines, or docs/plans/<ID>.md for cards ≥2d) + one test per `done` criterion. Plan mode + approval for P0, security, contract or experiment-integrity work.
2. Implement test-first in small steps; stay inside the card's scope.
3. Long or noisy runs → `test-runner` subagent (failures only come back).
4. Before finishing P0 or boundary work → `contract-guardian`. After touching factory, agent, MCP, gateway responses or prompts → `leakage-auditor`.
5. `/finish-task` → `/open-pr` (Om reviews with `/review-pr <n>`; Om's own boundary PRs get Kunal as reviewer). The human then runs `/clear`.
- Cards tagged `learn` are interview-critical: when `learn_mode: on`, explain the design and let the human write the core logic; you review, test and harden it.

## Token discipline
- Search first (`rg -n`, tight globs); read line ranges; don't re-read files already in context.
- Skip bulky paths: build/, .gradle/, node_modules/, .venv/, .next/, experiments/runs/, data/generated/, lockfiles, generated code.
- Summarize logs with commands (`make logs SVC=x TAIL=50`, `rg -n ERROR`); never paste raw logs or whole files back.
- Answer with diffs and short summaries, not full rewritten files.
- Respect the machine limits in `CLAUDE.local.md` (never start every compose profile on Om's 16 GB laptop).

## Definition of done
Every `done` criterion proven by a named test, command output or artifact · tests added · nested CLAUDE.md updated if layout or commands changed · board set to `review` with evidence (`done` after merge) · no claim beyond evidence · PR lists task, §, REQ/T IDs.
