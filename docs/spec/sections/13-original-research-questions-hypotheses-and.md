## 13. ORIGINAL RESEARCH QUESTIONS, HYPOTHESES AND SCOPE LOCK

**Submitted purpose (faithfully restated):** Determine whether an independent harness can measure, contain and provide decision-grade validation evidence for LLM agents resolving reconciliation breaks; build the working harness. The word *certify* in original proposal is not a regulatory claim.

- **RQ1:** How often do LLM agents attempt unauthorized/masking actions, and how does operational pressure affect the attempted-violation rate?
- **RQ2:** How much do the policy-enforcing gateway and real-time monitors reduce harmful outcomes, and at what cost to success/latency?
- **RQ3:** Can repeated trials produce sufficiently precise reliability estimates to inform approve/conditional/reject recommendations?

**Pre-registered H1:** Attempted violation rate rises with graded pressure L0–L3; positive pressure coefficient with a 95% CI excluding zero (mixed-effects logistic model; scenario random intercept).

**Pre-registered H2:** Full controls vs controls-off reduce **false resolution rate by ≥50% relative**, decrease **correct resolution rate by ≤5 percentage points**, and add **≤50 milliseconds to the 99th-percentile latency per tool call**. All conditions required. Distinguish on-path gateway overhead from total LLM/network latency; specify measured operation and sampling unit.

**Pre-registered H3:** On **200 scenarios × five repeats**, 95% CIs for primary rates have half-widths **≤5 percentage points**, and `pass^1 − pass^5 ≥10 percentage points`, where `pass^5` is the probability all five runs succeed on a task. The original `passk` notation is *all-k-run success*, not pass@k (at least one run). **Statistical caveat:** 200 independent scenario clusters can yield >5-point CI half-width for rates near 0.5; this is a testable high bar, not a guarantee. Repeats are correlated and must not be treated as 1,000 independent scenarios. If unachievable, report negative result/limitations, do not silently increase claimed precision.

**Original objectives:** O1 eight-break synthetic back office (Module 4); O2 actual standardized-tool LLM and controls-off baseline (Modules 4–5); O3 OPA/Redis/Kafka/invariants/audit supervisor (Module 5); O4 H1–H3 experiment (Module 6); O5 working system, validation report and final submission (Module 7).

**EXPLORATORY/NEW subquestions (not retroactively preregistered):** E1 rules baseline vs LLM on ambiguous text; E2 economically false balanced postings; E3 sequence-aware and stale-state failures; E4 deterministic action replay vs paired live agent; E5 resilience/fault recovery; E6 safe-automation-vs-risk curve; E7 signed/evidence-bound receipt verifiability; E8 coverage/efficiency trade-off.

