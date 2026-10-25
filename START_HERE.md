# START HERE — Second-Line Claude Code kit
Repo: https://github.com/omunite215/Project_SecondLine · The task split for Om and Kunal + a token-lean, gate-enforced Claude Code setup. There's no product code yet: the boards tell you (and Claude) what to build, in what order, and how to prove it's done.

## 1. Who puts which file where
| file(s) | Om | Kunal | in git? |
|---|---|---|---|
| everything in this kit (CLAUDE.md, .claude/settings.json, rules, skills, agents, hooks, tooling/, scripts/, docs/, Makefile, .github/, .vscode/) | same copy | same copy | yes — Om pushes it once |
| `CLAUDE.local.md` | copy `CLAUDE.local.md.om.example` | copy `CLAUDE.local.md.kunal.example` (fill chip/RAM) | no |
| `.claude/settings.local.json` | copy `.claude/settings.local.json.om.example` (your extra plugins + Trail of Bits marketplace) | copy `.claude/settings.local.json.kunal.example` (deny on held-out attack packs) | no |
| installed plugins + LSP binaries | `make skills-install BIN=1` | `make skills-install BIN=1` | no (your machine) |
| LangGraph skills in services/agent/.claude/skills/ | — | vendored by `make skills-install` | no (pinned in tooling/skills.lock.json, which is) |
| `gh auth login` | yes (admin) | yes (write) | no |
| `~/.ssh/config` alias `explorer` + key | yes (docs/setup/EXPLORER-HPC.md) | after the RC account is approved | no |
| GitHub collaborator, ruleset, `ai-review` label, `CLAUDE_CODE_OAUTH_TOKEN` secret | Om only (docs/setup/GITHUB.md) | — | repo settings |

## 2. Om — first day (≈45 min)
1. Unzip; the `Project_SecondLine/` folder is the repo root. Inside WSL: `cd ~/code && unzip …`, then `git init -b main`, `git remote add origin https://github.com/omunite215/Project_SecondLine.git`, commit, push. (If the remote already has commits, copy the files in instead — including the hidden `.claude/`, `.github/`, `.vscode/`, `.gitignore`, `.gitattributes`.)
2. Machine setup: docs/setup/OM-windows-wsl.md (WSL2 cap, toolchain, Claude Code CLI).
3. Personal files from the table above.
4. `gh auth login` → `make skills-install BIN=1` → `make skills-check` must print **GREEN**.
5. Open VS Code (WSL) → accept the workspace-trust prompt (project permissions and hooks need it) → the session opens with `[board]` and `[skills] GREEN` lines. Check `/context` (memory files) and `/hooks`.
6. GitHub: add Kunal (Write), create the ruleset + `ai-review` label (docs/setup/GITHUB.md), then run SH-01 with Kunal.

## 3. Kunal — first day (≈30 min)
1. Accept the collaborator invite → `git clone https://github.com/omunite215/Project_SecondLine.git`.
2. Machine setup: docs/setup/KUNAL-macos.md.
3. Personal files from the table above (fill chip/RAM).
4. `gh auth login` → `make skills-install BIN=1` → `make skills-check` must print **GREEN**.
5. Start VS Code from the terminal (`code .`), accept workspace trust, confirm `[skills] GREEN`.
6. File the Explorer access request (SH-19), then run SH-01 with Om.

## 4. Daily loop
`/next-task` (gate → card → plan) → build test-first → `/finish-task` → `/open-pr` → Om: `/review-pr <n>` → approve + merge → `/clear`. On days without a sync: `/standup`. HPC: `/hpc`.

## 5. The gate (why Claude may refuse to work)
Required skills per person: `tooling/claude-skills.json` (`make skills-list`). While they aren't installed and verified, the session says `[skills] RED`, `/next-task` stops, cards can't go `doing`, and hooks block project edits plus non-setup shell commands. Fix: `make skills-install` (+ `CARD=<ID>` for a card's task skills) → `make skills-check` → restart the session. Details: docs/team/SKILLS.md.

## 6. What Claude loads, and what it costs
| what | when | ≈ tokens |
|---|---|---|
| CLAUDE.md + CLAUDE.local.md + 4 subagent descriptions + `[board]`/`[skills]` lines | every session | ~2.9k (`make ctx`) |
| plugin skill descriptions (superpowers, pr-review-toolkit, …) | every session while enabled | ~2–4.5k (`/context`) |
| `.claude/rules/<topic>.md` (7) · `<area>/CLAUDE.md` (12) | only when a matching file is touched | 100–450 each |
| project skills `/next-task` … (9) | only when you type them | 150–400 each |
| one spec shard | only the one a card lists | 250–2,900 (24k master never loads) |

## 7. Token habits that matter most
- One task per session; `/clear` when the card is done; `/compact` only mid-task.
- Pick the model once per task (a switch re-sends the context uncached); Plan mode with a stronger model for P0 designs.
- Cards ≥2d live in docs/plans/<ID>.md — later sessions read the plan instead of re-planning.
- Ask for diffs, not files; let `test-runner` run suites and `spec-scout` answer spec questions.
- Disable task plugins when their card is done; `/skill-doctor` shows what each skill costs.

## 8. Open items for SH-01
Module 7 + milestone dates (PLAN.md §10) · Kunal's chip/RAM, GitHub handle, Explorer request · accept or override ADR-013/014/015.
