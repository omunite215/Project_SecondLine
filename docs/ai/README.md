# AI-assisted workflow (Claude Code)

Second-Line is built with Claude Code as a pair programmer, inside guardrails that keep it honest: a skills gate, hooks that block truth leakage, and a task board that says what to build and how to prove it's done. This folder holds the AI-facing files. The product itself never depends on them.

## What lives where
| file | purpose | loaded by Claude Code |
|---|---|---|
| `CLAUDE.md` (repo root) | one line, `@docs/ai/CLAUDE.md`. Claude Code only reads project memory from the root, so the root keeps an import stub | every session |
| `docs/ai/CLAUDE.md` | project rules: golden rules, who owns what, repo map, commands, working loop | every session (via the import) |
| `docs/ai/CLAUDE.local.md.{om,kunal}.example` | templates for each person's private `CLAUDE.local.md` (gitignored, at the root) | every session (your copy) |
| `.claude/` (hidden, root) | `settings.json` permissions, hooks, path-scoped `rules/`, project `skills/` (`/next-task`, `/open-pr`, …), review `agents/` | must stay at the root |
| `<area>/CLAUDE.md` (e.g. `services/ledger/`) | area notes next to the code they describe | when Claude touches that area |
| `tooling/claude-skills.json` + `skills.lock.json` | required plugins/skills per person, pinned upstream commits | by `make skills-check` |

## Personal files (not in git)
| file | Om | Kunal |
|---|---|---|
| `CLAUDE.local.md` | `cp docs/ai/CLAUDE.local.md.om.example CLAUDE.local.md` | `cp docs/ai/CLAUDE.local.md.kunal.example CLAUDE.local.md` (fill in chip/RAM) |
| `.claude/settings.local.json` | copy `.claude/settings.local.json.om.example` | copy `.claude/settings.local.json.kunal.example` |
| plugins + LSP binaries | `make skills-install BIN=1` | `make skills-install BIN=1` |
| `gh auth login` | yes (admin) | yes (write) |
| SSH alias `explorer` | docs/setup/EXPLORER-HPC.md | after the Research Computing account is approved |

Then `make skills-check` must print **GREEN**. Open VS Code (on Windows, inside WSL) and accept the workspace-trust prompt, since hooks need it. The session should open with `[board]` and `[skills] GREEN` lines.

## The gate (why Claude may refuse to work)
Required skills per person are listed in `tooling/claude-skills.json` (`make skills-list`). Until they're installed and verified:
- the session shows `[skills] RED`;
- `/next-task` stops, and cards can't go `doing`;
- hooks block project edits and any non-setup shell command.

Fix: `make skills-install` (add `CARD=<ID>` for a card's task skills), then `make skills-check`, then restart the session. Details: docs/team/SKILLS.md.

## Daily loop
`/next-task` (gate → card → plan) → build test-first → `/finish-task` → `/open-pr` → reviewer runs `/review-pr <n>` → approve → Om merges (docs/setup/GITHUB.md) → `/clear`. On days without a sync, use `/standup`; for HPC work, `/hpc`.

## What Claude loads, and what it costs
| what | when | ≈ tokens |
|---|---|---|
| CLAUDE.md stub + docs/ai/CLAUDE.md + CLAUDE.local.md + subagent descriptions + `[board]`/`[skills]` lines | every session | ~3k (`make ctx`) |
| plugin skill descriptions | every session while enabled | ~2–4.5k (`/context`) |
| `.claude/rules/<topic>.md` · `<area>/CLAUDE.md` | only when a matching file is touched | 100–450 each |
| project skills `/next-task` … | only when you type them | 150–400 each |
| one spec shard | only the one a card lists | 250–2,900 (the 24k master never loads) |

`make ctx` (in `make kit-check` and CI) fails if the always-loaded part goes over budget. It follows the root `@import`.

## Token habits that matter most
- One task per session. `/clear` when the card is done; use `/compact` only mid-task.
- Pick the model once per task, because a switch re-sends the context uncached. Use plan mode with a stronger model for P0 designs.
- Cards of 2 days or more live in `docs/plans/<ID>.md`, so later sessions read the plan instead of re-planning.
- Ask for diffs, not whole files. Let `test-runner` run suites and `spec-scout` answer spec questions.
- Disable task plugins when their card is done; `/skill-doctor` shows what each skill costs.
