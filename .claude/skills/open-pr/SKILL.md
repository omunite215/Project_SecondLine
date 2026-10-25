---
name: open-pr
description: Push the current branch and open a pull request with the repo template — Om reviews and merges every PR.
disable-model-invocation: true
argument-hint: "[TASK-ID]"
allowed-tools:
  - 'Bash(python3 "${CLAUDE_PROJECT_DIR}/scripts/board.py" *)'
  - 'Bash(python3 "${CLAUDE_PROJECT_DIR}/scripts/skills.py" *)'
  - 'Bash(python3 "${CLAUDE_PROJECT_DIR}/scripts/ctx.py" *)'
---
## Context
!`python3 "${CLAUDE_PROJECT_DIR}/scripts/ctx.py" git`
!`python3 "${CLAUDE_PROJECT_DIR}/scripts/ctx.py" gh-auth`
!`python3 "${CLAUDE_PROJECT_DIR}/scripts/board.py" show --doing $ARGUMENTS`

## Do this
1. Stop if: uncommitted changes (run /finish-task first), the branch is `main`, gh isn't logged in, or the card isn't `review` with evidence.
2. Write the PR body from .github/pull_request_template.md to a temp file: task ID, §, REQ/T IDs, one evidence line per `done` criterion, impact checks, handoff link.
3. Run (the human approves each prompt): `git push -u origin HEAD`, then `gh pr create --base main --title "<type(scope): ID summary>" --body-file <file> --reviewer omunite215`.
   If the human is Om: drop the self-review; add Kunal as reviewer when the diff touches services/gateway, services/ledger, services/mcp-adapter, infra/opa or .github.
4. Reply with the PR URL. Never approve, merge or push to main.
