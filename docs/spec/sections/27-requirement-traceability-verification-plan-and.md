## 27. REQUIREMENT TRACEABILITY, VERIFICATION PLAN AND FINAL PROJECT DEFINITION OF DONE

**Coverage map:**

| Requirement | Primary design sections | Minimum verifiable test(s) | Milestone |
|---|---|---|---|
| REQ-001 causal scenarios | §5–6 | T-DOM-02/03, T-EVAL-02 | M-1 |
| REQ-002 ledger/accounting | §5, §8–9 | T-DOM-01/05, T-SWE-02 | M-1 |
| REQ-003 rules benchmark | §10, §14 | T-AI-02 | M-1/M-4 |
| REQ-004 LLM tool use | §10 | T-AI-01 | M-2 |
| REQ-005 protected write | §8–9, §11 | T-SEC-01/02/04, T-SWE-02 | M-3 |
| REQ-006 independent truth | §5, §14 | T-DOM-03/04, T-AI-03 | M-1/M-4 |
| REQ-007 reproducibility/statistics | §13–14 | T-EVAL-01/02, T-DOC-01 | M-4 |
| REQ-008 events/supervisor | §7, §12 | T-SWE-01/03/05 | M-3 |
| REQ-009 receipts/audit | §9, §11–12 | T-SEC-05 | M-3/M-5 |
| REQ-010 control ablation | §10, §13–14 | T-EVAL-01 | M-4 |
| REQ-011 dual replay | §12, §17 | T-EVAL-03 | M-4 |
| REQ-012 attacks/chaos | §11, §15 | T-SEC-03/06, T-SWE-05 | M-4/M-5 |
| REQ-013 reviewer UI | §17 | T-UI-01/02 | M-5 |
| REQ-014 business/technical metrics | §14, §18 | T-EVAL-01, T-SWE-04 | M-4/M-5 |
| REQ-015 validation export | §17, §21 | T-DOC-01 | M-5 |
| REQ-016 trust bypass | §11 | T-SEC-01 | M-3 |

**Final definition of done** (completed claims must each link to commit/test logs/real measured artifact):

- [ ] All critical P0 requirements REQ-001–007, REQ-016 and defined acceptance tests genuinely pass.
- [ ] Actual LLM performs at least one complete tool-mediated case and safe abstention case, independently scored.
- [ ] Controls-off, monitor-only and full-control runs are evaluated on documented datasets; H1/H2/H3 supported or rejected with honest uncertainty.
- [ ] Ledger rejects unauthorized/stale/unsupported writes and handles duplicates across retries/concurrency; outbox and supervisor do not falsify financial state.
- [ ] Causal financial truth and evidence-only action contracts are separately reviewed; known incorrect balanced posting is caught by pre-commit evidence logic **or** by grader, with the detection gap acknowledged.
- [ ] Counterfactual replay has explicit same-actions and independent live-agent modes, with reliable snapshot isolation and state comparisons.
- [ ] Reviewer can trace any showcased action from model proposal to OPA decision, verified evidence, database state, monitor, receipt and grade.
- [ ] Release reproduces at least a smoke result and a 5–7-minute local demo without depending on HPC availability.
- [ ] Source citations/standards, original POC discrepancy, experiment amendments and known limitations are transparently documented.
- [ ] GitHub README and demo explain real findings, limits and each teammate's defensible contributions; no untested production/regulatory claims.

**Automated document QA checks (apply when updating this master spec):** Verify sections 0–27 each appear exactly once; requirements 001–016 all mapped to tests and milestones; B1–B8, H1–H3, RQ1–RQ3, metrics, both replay modes and all P0/P1 upgrades appear; original 3,000+300 experiment math and 34 historical references preserved; JSON parseable; Markdown code fences balanced; original data sources/risk controls/tools/modules/personas covered; planned vs historical vs new claims distinguishable; no placeholder sources masquerading as validated. After any edit, rerun a structural checker and perform a separate human semantic review. **Document checks cannot establish that the actual software is correct.**

---

**END OF CANONICAL MASTER SPECIFICATION.** Only modify with a versioned change log and explicit decisions; never substitute a generated midterm report or source-code assumptions for this document.
