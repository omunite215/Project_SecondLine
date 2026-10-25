# experiments — prereg, configs, manifests, results (owner: Kunal)
prereg/preregistration.md (draft) · prereg/frozen/<date>/ (IMMUTABLE, deny-listed) · configs/*.yaml (frozen once a campaign starts) · manifests/ · results/<campaign>/ (aggregates, committed) · runs/ (raw, gitignored) · anchors/ (audit checkpoints)
Never pull runs/ raw logs into context — use `make analyze` or a script that prints a summary. Rules: .claude/rules/experiment-integrity.md.
