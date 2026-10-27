---
name: next-task
description: Pick up the next task from my board and start it with a short plan, after the skills gate.
disable-model-invocation: true
argument-hint: "[TASK-ID]"
allowed-tools:
  - 'Bash(python3 "${CLAUDE_PROJECT_DIR}/scripts/board.py" *)'
  - 'Bash(python3 "${CLAUDE_PROJECT_DIR}/scripts/skills.py" gate *)'
  - 'Bash(python3 "${CLAUDE_PROJECT_DIR}/scripts/ctx.py" *)'
---
## Skills gate
!`python3 "${CLAUDE_PROJECT_DIR}/scripts/skills.py" gate --next $ARGUMENTS`

## Board
!`python3 "${CLAUDE_PROJECT_DIR}/scripts/board.py" next $ARGUMENTS`

## Do this
0. Gate RED → STOP. Show the human the fix commands it printed, nothing else.
1. A card is `doing` → continue it (if docs/plans/<ID>.md exists, resume it with superpowers:executing-plans). Otherwise take the first unblocked card (or the ID given); deps not done → name them and stop.
2. Read only: the nested CLAUDE.md for each path in `build`, the § shards in `refs` (docs/spec/INDEX.md; `spec-scout` for more than 2 shards), the contract schemas involved, and the skills on the card's `skills:` line.
3. Plan: card < 2d → ≤10 bullets here. Card ≥ 2d → superpowers:writing-plans into docs/plans/<ID>.md (files, test-first steps, verification commands). superpowers:brainstorming only when the card leaves a design decision open. Name the test that proves each `done` criterion. P0, security, contract or experiment-integrity card → wait for approval before editing.
4. On approval: `python3 scripts/board.py set <ID> doing` (it re-checks the card's skills) on branch `<owner>/<ID>-<slug>`.
