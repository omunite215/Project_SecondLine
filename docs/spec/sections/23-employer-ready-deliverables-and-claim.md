## 23. EMPLOYER-READY DELIVERABLES AND CLAIM HYGIENE

**Minimum GitHub evidence:** Runnable source with explicit real-vs-stub modules, versioned scripts, design diagrams, schemas, threat model, transactions/idempotency tests, benchmark harness, evaluation manifest and artifacts, representative failure trace, state-diff screenshot/video, technical tradeoffs and limitations. Provide demo video (~5–7 min), short case study for recruiters and extended README/ADRs for engineers. If potential collaboration with FINOS, contribute only after quality/review; external adoption is not assumed.

**Interview stories must be demonstrable:** Why an LLM beat/failed rules; how transaction+outbox prevented event-loss inconsistency; why p99 overhead was measured separately; how balanced wrong entries evade simple invariants; why kill switch cannot prevent earlier commits; how approval state hashes prevent TOCTOU; how replay isolates policy from model adaptation; why clustered CIs matter; which failures remained.

**Do not manufacture resume bullets.** After real measurement, express demonstrable outcomes (e.g., measured safe coverage, harm reduction, system latency, integration tests, throughput) with exact denominators and settings. Distinguish student's engineering from bank-grade production systems. A polished interface without working controls is weaker than a correct backend with a clear recorded demo.

**Suggested defensible summary after implementation (edit based on results):** "Built a synthetic cash-equity reconciliation assurance platform that evaluates LLM tool actions against independent financial ground truth, mediates high-risk writes through policy/evidence validation, and produces replayable, auditable traces. Compared real agents and rules baselines on held-out scenarios with repeated-trial reliability metrics." The tense must match what has actually been completed.

