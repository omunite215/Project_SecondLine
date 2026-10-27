---
name: finish-task
description: Close the current task — verify done criteria, review, update board and docs, then hand off to /open-pr.
disable-model-invocation: true
argument-hint: "[TASK-ID]"
allowed-tools:
  - 'Bash(python3 "${CLAUDE_PROJECT_DIR}/scripts/board.py" *)'
  - 'Bash(python3 "${CLAUDE_PROJECT_DIR}/scripts/skills.py" gate *)'
  - 'Bash(python3 "${CLAUDE_PROJECT_DIR}/scripts/ctx.py" *)'
---
## Context
!`python3 "${CLAUDE_PROJECT_DIR}/scripts/board.py" show --doing $ARGUMENTS`
!`python3 "${CLAUDE_PROJECT_DIR}/scripts/ctx.py" git`

## Do this
1. superpowers:verification-before-completion — run the test, command or artifact that proves each `done` criterion (suites via `test-runner`). Missing evidence ⇒ not done: list what's left and stop.
2. Reviews: P0 or trust-boundary card → `contract-guardian` (Om: plus differential-review on the diff); factory, agent, MCP, gateway responses or prompts → `leakage-auditor`; security cards → insecure-defaults. Then superpowers:requesting-code-review and fix what it finds.
3. Layout or commands changed → update the nested CLAUDE.md; contracts changed → `/handoff`; refs changed → `make trace`.
4. `python3 scripts/board.py set <ID> review --evidence "<tests/artifacts>"` (`done` after merge).
5. Draft the Conventional Commit `type(scope): <ID> summary`, commit, then run `/open-pr`.
6. Task plugins this card used that no other `doing` card needs → suggest `claude plugin disable <name>@<marketplace> --scope local` (token hygiene).
