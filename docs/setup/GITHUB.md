# GitHub & CI/CD (owner: Om, OM-25) — https://github.com/omunite215/Project_SecondLine

## Roles
- **Om:** repo admin; owns `.github/` and CI; approves and merges every PR. His own PRs need green CI, and he requests Kunal's review when they touch services/gateway, services/ledger, services/mcp-adapter, infra/opa or .github (independent review of the controls, §0). He then merges through the ruleset bypass.
- **Kunal:** Write access; branches `kunal/<ID>-slug`; PRs via `/open-pr`; never pushes to main.

## One-time setup (Om)
1. **Collaborator:** Settings → Collaborators → add Kunal with Write. He works in this repo, not a fork, so Actions and secrets work on his PRs.
2. **Merging:** Settings → General → allow squash merging only; turn on "Automatically delete head branches".
3. **Ruleset** (Settings → Rules → Rulesets → new branch ruleset "main", target the default branch):
   - Restrict deletions and block force pushes.
   - Require a pull request: 1 approval, dismiss stale approvals on new commits, require review from Code Owners, require conversation resolution.
   - Required status checks (branch must be up to date before merging): `kit`, then add java / python / policy / console as those jobs appear.
   - Bypass list: Repository admin, for pull requests only.
   - Rulesets on a private repo need GitHub Pro, which is free with the Student Developer Pack.
4. **Labels:** create `ai-review`.
5. **AI first-pass review** (optional; it uses Om's Claude usage):
   - In Claude Code, run `/install-github-app` to install the Claude GitHub App on the repo.
   - Settings → Environments → new environment `claude-review`, with yourself as required reviewer.
   - Add the secret `CLAUDE_CODE_OAUTH_TOKEN` (made with `claude setup-token`, Pro/Max) to that **environment**, not to the repo. A same-repo PR can edit the workflow and drop the label check, so the environment approval is the real gate.
   - To use an API key instead, add `ANTHROPIC_API_KEY` and switch the workflow input to `anthropic_api_key`.
   - Label a PR `ai-review` to run `.github/workflows/claude-review.yml`.
6. **gh CLI:** run `gh auth login` in your own terminal. Claude can read PRs through `gh` but can't read your token (deny-listed).

## Flow
- **Kunal:** `/finish-task` → `/open-pr` → CI → Om runs `/review-pr <n>` → Om runs `gh pr review <n> --approve` (or `--request-changes`) → squash merge → `python3 scripts/board.py set <ID> done`.
- **Om:** the same flow, with Kunal as reviewer on boundary paths, merging via bypass once CI is green.

## Required checks (grow with OM-25)
`kit` now. Later `java` (Gradle + Testcontainers), `python` (uv + pytest), `policy` (opa test), `console` (pnpm + Playwright), `leakage` (KG-05) and contracts drift. Each becomes required in the ruleset the day it exists.
