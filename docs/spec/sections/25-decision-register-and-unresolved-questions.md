## 25. DECISION REGISTER AND UNRESOLVED QUESTIONS

**Adopted now (not evidence of implementation):**

| Decision ID | Decision and tradeoff | State |
|---|---|---|
| ADR-001 | Keep one-bank cash-equity reconciliation; platform abstraction is secondary | ADOPTED |
| ADR-002 | Java/Spring/Postgres holds financial authority; Python/LangGraph does not write DB directly | ADOPTED |
| ADR-003 | Use actual LLM tool calls plus deterministic rules baseline | ADOPTED |
| ADR-004 | Pre-commit domain/evidence checking mandatory; async Kafka monitor cannot retroactively stop commit | ADOPTED |
| ADR-005 | MCP tools versioned, independently authenticated and least-privilege | ADOPTED |
| ADR-006 | Independent financial truth grader; balance alone insufficient | ADOPTED |
| ADR-007 | Two different replay modes, isolated state reset | ADOPTED |
| ADR-008 | Keep registered H1–H3 and disclose amendments/exploration | ADOPTED |
| ADR-009 | Docker Compose before Kubernetes; local live demo has model fallback | ADOPTED |
| ADR-010 | Prioritize proof over extra buzzword frameworks | ADOPTED |
| ADR-011 | Approval digest binds action + evidence version + state; durable idempotency in DB | ADOPTED |
| ADR-012 | Audit receipts include denied actions; independent signed checkpoint as time allows | ADOPTED |

**Unresolved; decide before implementing affected interfaces:**

1. **Precise accounting model:** Cash versus securities double-entry and position projection; selected account chart, price precision and permitted adjustment categories. Have domain reviewer confirm, document ADR.
2. **Baseline model IDs:** Open-weight model available on Explorer, GPU RAM and Slurm queue access, frontier provider cost/quotas and local fallback. Select by measured reliability/tool support, not brand.
3. **MCP spec and transport:** Pin current tested SDK/revision, local vs remote auth scheme and schema compatibility; do not hardcode against obsolete examples.
4. **Policy/identity:** Exact role-action-policy matrix, approval thresholds, allowable suspense account actions; no unreviewed magic numbers.
5. **Evidence semantics:** Which record is authoritative for which break; when an incorrect state can be detected synchronously vs only by hidden oracle (the runtime verifier cannot use inaccessible omniscient truth).
6. **Per-hypothesis denominators:** H1 applicable proposal counts, H2 false/correct resolution denominators and gateway p99 start/end timestamps, H3 pass^5 estimator. Freeze before main evaluation.
7. **Research amendments:** Whether to add paired-pressure experiment independently or revise factorial assignment; additional runs and explanation of effects on pre-registered results.
8. **External validation:** Whether a finance practitioner/classmate can provide blind scenarios; if unavailable, disclose limitation.
9. **Audit threat model:** Signature key storage, verification/anchoring technique (local vs external), which attacker model is demonstrably addressed; avoid overclaiming.
10. **Contract versioning:** Use one stable API v1 or v2 with idempotency/reason-code support; original legacy v1/v2 deprecation demo is **lower priority** than safety. Record if omitted and how archived runs are replayed.
11. **Metrics and budgets:** Numerical limits for latency/cost, observability retention, workload, and fallback thresholds grounded in pilot measurements.
12. **Team assignments:** Confirm original assumed split and milestones with both contributors.
13. **Source reconciliation:** Resolve historical PoC 1,035 vs 729 count, check code/labels in original Fig. 4/Table 6, and confirm official settlement codes/mappings.

