---
name: handoff
description: Write a handoff note to the teammate about an interface or contract change, or a blocker.
disable-model-invocation: true
allowed-tools:
  - 'Bash(python3 "${CLAUDE_PROJECT_DIR}/scripts/board.py" *)'
  - 'Bash(python3 "${CLAUDE_PROJECT_DIR}/scripts/skills.py" gate *)'
  - 'Bash(python3 "${CLAUDE_PROJECT_DIR}/scripts/ctx.py" *)'
argument-hint: "<topic>"
---
Create `docs/team/handoffs/<YYYY-MM-DD>-<from>-to-<to>-<slug>.md` (from = `owner:` in CLAUDE.local.md), ≤40 lines:
- **What changed** — contracts VERSION, endpoints, schemas, env vars; task ID + ADR.
- **How to use it now** — one example request/response or command.
- **Breaking?** — migration steps; which mocks/fixtures/examples were updated (paths).
- **What I need back** — by which task ID; open questions.
Then add `Handoff: <path>` to the PR description.
