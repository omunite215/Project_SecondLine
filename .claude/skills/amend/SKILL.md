---
name: amend
description: Record an experiment AMENDMENT or exploratory analysis without touching the frozen preregistration.
disable-model-invocation: true
allowed-tools:
  - 'Bash(python3 "${CLAUDE_PROJECT_DIR}/scripts/board.py" *)'
  - 'Bash(python3 "${CLAUDE_PROJECT_DIR}/scripts/skills.py" *)'
  - 'Bash(python3 "${CLAUDE_PROJECT_DIR}/scripts/ctx.py" *)'
argument-hint: "<short title>"
---
!`python3 "${CLAUDE_PROJECT_DIR}/scripts/ctx.py" ls experiments/prereg/frozen`

Never edit experiments/prereg/frozen/**. Append to docs/experiment-amendments.md (create it if missing):
## AMENDMENT-<n> · <title> (YYYY-MM-DD)
- Type: AMENDMENT (changes the registered design) | EXPLORATORY (new analysis only)
- What changes vs the frozen prereg (quote the section and line)
- Rationale — and was it decided before or after seeing which results? Say so explicitly.
- Affected hypotheses/metrics; how pre- and post-amendment results will both be reported
- Approved by: om ☐ kunal ☐ (both required)
