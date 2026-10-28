# GitHub & CI/CD (owner: Om, OM-25) — https://github.com/omunite215/Project_SecondLine

Source of truth: **`.github/settings.json`** (merge options, collaborators, labels, the `claude-review` environment, every ruleset). `make gh-check` diffs it against the live repo (Om's admin `gh` session; exit 1 on any gap, gh error or non-admin view). `make gh-apply` prints the writes that would reconcile it; `python3 scripts/gh_settings.py apply --yes` makes them. CI can't run `gh-check` (its token can't see bypass actors), so run it after every settings change and before each milestone gate. `tests/kit/test_om_25_ci_guards.py` pins the values below in `make kit-check`.

## Roles (maker/checker, §21)
- **Om:** repo admin; owns `.github/` and CI; the only person who can merge to `main`. Every PR he authors needs **Kunal's** approval and green, up-to-date CI.
- **Kunal:** Write access; branches `kunal/<ID>-slug`; PRs via `/open-pr`; can't merge or push to `main` (ruleset `merge-gate`). Every PR he authors needs **Om's** approval.
- Neither can approve a PR whose last push is their own (`require_last_push_approval`), so nobody approves their own code.
- Review every PR within 24 h with `/review-pr <n>`.

## Rulesets
| ruleset | target | rules | bypass |
|---|---|---|---|
| `main` | default branch | no deletion · no force push · PR with 1 approval, stale approvals dismissed, code-owner review, last-push approval, conversations resolved, squash only · required checks (strict: branch up to date) | none |
| `merge-gate` | default branch | restrict updates | Repository admin, pull requests only |
| `gate-tags-create` | `refs/tags/m*` | restrict creation | Repository admin, always |
| `gate-tags-immutable` | `refs/tags/m*` | no update · no deletion · no force push | none |

Rulesets evaluate independently: when Om merges, `merge-gate` shows `bypass` in the rule-suite log (by design) while `main` must still `pass`. A `main` = `bypass` entry means something is wrong. Rulesets on a private repo need GitHub Pro (free with the Student Developer Pack).

## One-time setup (Om, already done unless `make gh-check` says otherwise)
1. **Collaborator:** Settings → Collaborators → Kunal with Write. He works in this repo, not a fork, so Actions and secrets work on his PRs.
2. **Merging:** squash only; "Automatically delete head branches" on; auto-merge off.
3. **Rulesets + label:** `make gh-apply`, review, then `python3 scripts/gh_settings.py apply --yes`. It creates new restrictions before removing old bypasses, so there's no window where Kunal can merge.
4. **AI first-pass review** (optional; uses Om's Claude usage):
   - In Claude Code, run `/install-github-app` to install the Claude GitHub App on the repo.
   - Environment `claude-review` with a deployment-branch policy allowing only `main`. Put the token there, never in repo secrets: a repo secret is readable by any workflow on a same-repo PR. In your own terminal: `gh secret set CLAUDE_CODE_OAUTH_TOKEN --env claude-review` (value from `claude setup-token`, Pro/Max).
   - The workflow uses `pull_request_target` (runs from protected `main`, so a PR can't edit it) and only runs when **Om** adds the `ai-review` label. Required reviewers would need GitHub Enterprise on a private repo; the branch policy doesn't. Never add `ref:` to its checkout.
   - To use an API key instead, add `ANTHROPIC_API_KEY` and switch the workflow input to `anthropic_api_key`.
5. **gh CLI:** run `gh auth login` in your own terminal. Claude can read PRs through `gh` but can't read your token (deny-listed).

## Flow
- **Kunal's PR:** `/finish-task` → `/open-pr` → CI → Om runs `/review-pr <n>` → `gh pr review <n> --approve` (or `--request-changes`) → Om squash-merges → `python3 scripts/board.py set <ID> done`.
- **Om's PR:** `/open-pr` with Kunal as reviewer → CI → Kunal approves → Om squash-merges.
- **Dependabot PR:** Om reviews and approves → Om merges. When two touch neighbouring lines, merge one, comment `@dependabot rebase` on the other, re-approve after its CI.
- Branch behind `main`? Update it (`gh api -X PUT repos/omunite215/Project_SecondLine/pulls/<n>/update-branch`) and wait for CI; there's no way around the strict check.

## Milestone tags
At each gate (§5 of PLAN.md) Om tags the merge commit: `git tag -a m0 -m "M-0 gate" <sha> && git push origin m0`. Only Om can create `m*` tags, and nobody can move or delete them once pushed. Never push a throwaway `m*` tag.

## Required checks (grow with the services)
`kit` now. Later `java` (Gradle + Testcontainers), `python` (uv + pytest), `policy` (opa test), `console` (pnpm + Playwright), `leakage` (KG-05) and contracts drift. The day a job exists, add its id to `main`'s `required_status_checks` in `.github/settings.json`, apply, and `make gh-check`. `test_OM_25_required_checks_are_pr_jobs` fails if a required check names a job that doesn't run on `pull_request`, which would block every merge. `test_OM_25_dependabot_covers_build_files` fails if a `build.gradle.kts`, `pyproject.toml` or `package.json` lands without a Dependabot entry.

## Break-glass
Only when a merge can't wait for the other person (e.g. submission deadline, Kunal unreachable): Om adds himself as a bypass actor on `main` in the GitHub UI, merges, removes it, and adds a row below. `make gh-check` stays red until the bypass is removed.

### Break-glass log
| date | PR | why | bypass removed |
|---|---|---|---|
