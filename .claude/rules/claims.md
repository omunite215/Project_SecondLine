---
paths:
  - "README.md"
  - "ARCHITECTURE.md"
  - "docs/*.md"
  - "docs/report/**"
  - "docs/datasheets/**"
  - "docs/model-cards/**"
  - "experiments/results/**"
---
# Claim hygiene for prose (§0, §2, §16, §23)
- Every number states its denominator and settings and links its manifest/result file.
- Label provenance: REAL LLM RUN · SCRIPTED · SIMULATED · POC-REPORTED · PLANNED · EXPLORATORY · AMENDMENT · VERIFY.
- Never write "certified", "bank-safe", "regulator-approved", "prevents all fraud", "production-ready", a p99 or a run count that wasn't measured.
- PoC figures (2,400 scripted runs; 1,035 vs 729) are POC-REPORTED, never LLM findings.
- Don't claim novelty for state-based agent evaluation (τ-bench grades final DB state); claim the finance-grounded composition.
- Regulatory/industry statements are context. Mapping ≠ compliance.
