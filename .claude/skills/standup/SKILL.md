---
name: standup
description: Draft a short async standup from recent commits and board status.
disable-model-invocation: true
allowed-tools:
  - 'Bash(python3 "${CLAUDE_PROJECT_DIR}/scripts/board.py" *)'
  - 'Bash(python3 "${CLAUDE_PROJECT_DIR}/scripts/skills.py" *)'
  - 'Bash(python3 "${CLAUDE_PROJECT_DIR}/scripts/ctx.py" *)'
---
!`python3 "${CLAUDE_PROJECT_DIR}/scripts/ctx.py" standup`
!`python3 "${CLAUDE_PROJECT_DIR}/scripts/board.py" summary --brief`
!`python3 "${CLAUDE_PROJECT_DIR}/scripts/board.py" brief`

Write ≤8 lines for my teammate: done (task IDs), doing, next, blockers/needs (with task IDs), interface changes (handoff links). No filler.
