---
name: adr
description: Create or update an Architecture Decision Record and the decision register.
disable-model-invocation: true
allowed-tools:
  - 'Bash(python3 "${CLAUDE_PROJECT_DIR}/scripts/board.py" *)'
  - 'Bash(python3 "${CLAUDE_PROJECT_DIR}/scripts/skills.py" *)'
  - 'Bash(python3 "${CLAUDE_PROJECT_DIR}/scripts/ctx.py" *)'
argument-hint: "<title or ADR number>"
---
!`python3 "${CLAUDE_PROJECT_DIR}/scripts/ctx.py" ls docs/adr`

1. New ADR → next free number after the highest in docs/adr/README.md; copy docs/adr/TEMPLATE.md to `docs/adr/ADR-NNN-<slug>.md`. Existing ADR → edit in place.
2. Fill: context (cite spec § and the U#/ADR it resolves), ≤3 options with tradeoffs, decision, consequences (tests + tasks affected), verification. Status PROPOSED.
3. Add or update its row in docs/adr/README.md. ACCEPTED only when both owners approve the PR.
4. If it changes a trust boundary or a contract: list affected task IDs and run `/handoff`.
