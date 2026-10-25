---
name: review-pr
description: Approver review of a pull request (Om) — CI, card evidence, scope, contracts, security — ending in a verdict and the gh command to run.
disable-model-invocation: true
argument-hint: "<PR number>"
allowed-tools:
  - 'Bash(python3 "${CLAUDE_PROJECT_DIR}/scripts/board.py" *)'
  - 'Bash(python3 "${CLAUDE_PROJECT_DIR}/scripts/skills.py" gate *)'
  - 'Bash(python3 "${CLAUDE_PROJECT_DIR}/scripts/ctx.py" *)'
---
## Pull request
!`python3 "${CLAUDE_PROJECT_DIR}/scripts/ctx.py" pr $ARGUMENTS`

## Do this
1. CI: any failing or pending check → verdict WAIT; stop here.
2. Card: take the task ID from the title/body → `python3 scripts/board.py show <ID>`. Every `done` criterion needs an evidence line in the PR body; missing → REQUEST CHANGES.
3. Diff (`gh pr diff $ARGUMENTS`): pr-review-toolkit agents (code-reviewer, silent-failure-hunter, pr-test-analyzer; type-design-analyzer for new types); Trail of Bits differential-review when paths include services/gateway, services/ledger, services/mcp-adapter, infra/opa or .github; `contract-guardian` when packages/contracts or a write path changes; `leakage-auditor` when factory, agent, prompts or MCP descriptions change.
4. Scope: files outside the author's area (CLAUDE.md "Who is who") need a stated reason; experiment-integrity changes need an AMENDMENT link.
5. Output: verdict APPROVE | REQUEST CHANGES | WAIT; ≤10 comments (file:line — issue — fix); the review text in a temp file; then the command for Om: `gh pr review $ARGUMENTS --approve|--request-changes --body-file <file>`. Never approve or merge yourself — the permission prompt is Om's decision.
