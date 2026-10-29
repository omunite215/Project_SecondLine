# Claude skills & plugins — what we use, why, how (gate-enforced)

**Source of truth:** `tooling/claude-skills.json` · **Install:** `make skills-install` (in YOUR terminal — plugins run code with your privileges) · **Verify:** `make skills-check` · **Yours:** `make skills-list`

While the gate is RED: the session opens with `[skills] RED`, `/next-task` stops, `board.py set <ID> doing` refuses, and PreToolUse hooks block project edits and non-setup shell commands. Only setup docs stay editable (docs/setup/, this file, CLAUDE.local.md, docs/ai/README.md) so Claude can help fix the setup; the guardrails themselves (.claude/, tooling/) stay locked, and only setup/read-only commands run (no expansion, redirects other than `2>&1`, or flags that write files or run programs). The gate re-verifies every 48 h, whenever the manifest changes, and whenever a card with task skills goes `doing`.

## 1. The set
| skill / plugin | who | tier | for |
|---|---|---|---|
| `superpowers` (official marketplace → obra/superpowers, MIT) | both | core | TDD, systematic debugging, verification, plans, code-review discipline |
| `pyright-lsp` | both | core | Python diagnostics (binary `pyright-langserver`) |
| `jdtls-lsp` | Om | core | Java diagnostics (binary `jdtls`) |
| `typescript-lsp` | Om | core | TypeScript diagnostics (binary `typescript-language-server`) |
| `pr-review-toolkit` | Om | core | review agents for approving every PR |
| `security-guidance` | Om | core | vulnerability review of Claude's own edits (gateway, ledger, OPA, CI) |
| `differential-review` (trailofbits/skills) | Om | core | security diff review with blast radius, inside `/review-pr` |
| `insecure-defaults` (trailofbits/skills) | Om | task: OM-05/07/10/15 | fail-open defaults, hardcoded credentials, weak auth |
| `mcp-server-dev` | Om | task: OM-06 | MCP server patterns for the adapter |
| `frontend-design` | Om | task: OM-21/22 | console UI |
| `document-skills` (anthropics/skills) | both | task: SH-15/16 | docx / pdf / pptx deliverables |
| `langgraph-fundamentals`, `langgraph-persistence` (langchain-ai/langchain-skills, vendored) | Kunal | core | current LangGraph APIs, checkpointers, interrupts |

Built in, no install: `/code-review`, `/doctor`, `/skill-doctor`, `/context`, `/usage`. Project skills: `/next-task` `/finish-task` `/open-pr` `/review-pr` `/handoff` `/adr` `/amend` `/standup` `/hpc`.

## 2. How to use them — their documented workflows, mapped to our loop
**superpowers**
- `test-driven-development` — every code change: write the failing test, watch it fail, minimal code, green, refactor. Test names carry spec IDs (`T_SWE_02_…`).
- `systematic-debugging` — any failing test or build: reproduce → isolate → hypothesis → verify → fix. No shotgun edits.
- `verification-before-completion` — before `/finish-task`, before saying "passes/works/done", before `/open-pr`: run the proof commands and show their results.
- `writing-plans` → `executing-plans` — cards ≥ 2d: write `docs/plans/<ID>.md` (bite-sized steps, exact files, verification commands), then execute it across sessions. The next session reads the plan instead of re-planning — that's a token saver, not a cost.
- `requesting-code-review` / `receiving-code-review` — before `/open-pr`, and when Om's review comes back.
- `brainstorming` — only when a card leaves a real design decision open (ADR cards such as SH-03/04/05/09, model selection in KG-10). Elsewhere the card + § shards are the approved design; CLAUDE.md overrides skill defaults.
- `using-git-worktrees`, `subagent-driven-development` — optional for Kunal; avoid on Om's 16 GB laptop (duplicate Gradle builds, many parallel subagents).

**LSP plugins** — terminal sessions get diagnostics and go-to-definition: after an edit, read the diagnostics instead of running a full build. In the VS Code panel, Claude also sees VS Code's own diagnostics, so install the recommended extensions (`.vscode/extensions.json`).

**Om — approver toolkit.** `/review-pr <n>` chains: CI checks → card evidence → `pr-review-toolkit` agents → `differential-review` on boundary paths → `contract-guardian` / `leakage-auditor` → verdict + the `gh pr review` command you run yourself. `security-guidance` stays on while you write gateway, ledger, OPA and workflow code. Run `insecure-defaults` on the security cards before `/finish-task`. Use `mcp-server-dev` while building OM-06 and `frontend-design` for OM-21/22.

**Kunal.** The LangGraph skills auto-load whenever Claude touches services/agent — use them over memory for StateGraph, Command/Send, checkpointers and interrupts (KG-08: approval waits + resume by run_id). They're pinned in `tooling/skills.lock.json`, which your first `make skills-install` writes: commit it (the gate stays RED for an unpinned vendored skill). `make skills-update` re-pins, then open a PR.

**Both.** `document-skills` only for SH-15/16 files. `/finish-task` reminds you to disable task plugins afterwards: `claude plugin disable <name>@<marketplace> --scope local`.

## 3. Token cost (check `/context` and `/skill-doctor`)
Each enabled plugin adds its skill/agent descriptions to every session; superpowers also injects a short primer at session start. Rough adds: superpowers 2–4k tokens · pr-review-toolkit ~0.5k · LSP plugins ≈0 (no text) · task plugins only while installed and enabled. Disable task plugins when their card is done.

## 4. Install details
- Claude Code CLI ≥ 2.1.292 on PATH: `curl -fsSL https://claude.ai/install.sh | bash`. The VS Code extension alone may not provide `claude`; the gate and hooks need it.
- `make skills-install BIN=1` also installs LSP binaries where it can (npm / uv / curl).
- jdtls by hand (WSL): `mkdir -p ~/.local/share/jdtls ~/.local/bin && curl -fsSL https://download.eclipse.org/jdtls/snapshots/jdt-language-server-latest.tar.gz | tar -xz -C ~/.local/share/jdtls && ln -sf ~/.local/share/jdtls/bin/jdtls ~/.local/bin/jdtls` (needs Java 21 + python3; keep `~/.local/bin` on PATH). macOS: `brew install jdtls`.
- A card's task skills: `make skills-install CARD=OM-06`.
- macOS: start VS Code from a terminal (`code .`) so Homebrew/npm paths reach Claude Code.
- Marketplaces: `claude-plugins-official` (built in), `anthropics/skills` (`anthropic-agent-skills`), `trailofbits/skills` (`trailofbits`). Read a plugin's README before installing.

## 5. Troubleshooting
- "enabled in project settings but isn't installed" → `make skills-install`.
- Gate still RED right after installing → restart the session (or `/reload-plugins`), then `make skills-check`.
- A plugin was renamed or moved upstream → fix `tooling/claude-skills.json` in a PR (both approve). Never bypass the gate locally.
