---
paths:
  - "experiments/**"
  - "packages/evaluation/**"
  - "services/agent/src/sl_agent/prompts/**"
  - "packages/scenario-factory/src/sl_factory/splits*"
---
# Experiment integrity (§13–14, NFR-07, ADR-008)
- Frozen = immutable: experiments/prereg/frozen/** and any campaign config a started campaign references.
- No tuning on eval/blind and no reading their data. Prompts, few-shots and monitor thresholds use the dev split.
- Every run has a manifest (model ID + settings, prompt/tool/policy hashes, seed, snapshot hash, host). No manifest = the run doesn't count.
- Retry infrastructure failures only; never re-roll a bad outcome. Log every deviation from plan.
- Repeats are correlated: cluster by scenario; 5 repeats are not 5 independent samples.
- Use the prereg denominators verbatim. pass^k = all k runs succeed (not pass@k).
- Report null/negative results as prominently as positive ones. Exploratory ≠ confirmatory.
