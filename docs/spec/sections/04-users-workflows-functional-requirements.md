## 4. USERS, WORKFLOWS, FUNCTIONAL REQUIREMENTS

| ID | User story / behavior | Priority |
|---|---|---|
| REQ-001 | Generate realistic **causal** synthetic worlds with full hidden ground truth and visible bank/custodian evidence | P0 |
| REQ-002 | Model valid ledger events, trading/settlement states, journal entries, immutable audit history and as-of snapshots | P0 |
| REQ-003 | Offer deterministic rule-based reconciliation benchmark with identical evidence/access boundaries | P0 |
| REQ-004 | Run real tool-using LLM via LangGraph; read/explain/act/escalate exclusively through constrained MCP tools | P0 |
| REQ-005 | Apply authenticated authorization, per-run/action scope, pre-commit business checks and durable idempotency | P0 |
| REQ-006 | Grade each attempted/executed action and final case **independently** from canonical truth; allow abstention/escalation | P0 |
| REQ-007 | Support frozen experiments, seeded reruns, model/prompt/tool/policy manifests and confidence intervals | P0 |
| REQ-008 | Emit reliable outbox events, Kafka publication, asynchronous cross-action monitors and safe kill-switch behavior | P1 |
| REQ-009 | Create machine-verifiable decision receipts and tamper-evident append-only audit history | P1 |
| REQ-010 | Run controls-off / monitor-only / full-controls comparisons, plus separate rules baseline | P1 |
| REQ-011 | Support **deterministic action replay** and **paired live counterfactual executions** from reset initial state | P1 |
| REQ-012 | Run finance-specific adversarial, prompt-injection, stale-state and chaos experiments | P1 |
| REQ-013 | Provide reviewer evidence, approval/reject reason codes, protected operations, real-time trace, role-based UI | P2 (minimum simple UI P1) |
| REQ-014 | Report cost, correct/false closure, escalation, reliability, tool latency, event lag and recovery correctness | P1 |
| REQ-015 | Export reproducible validation package: benchmark/datasheet/model card/risk-control mapping/audit proof | P1 |
| REQ-016 | Test bypass attempts and forbid unmediated writing to ledger with agent identity | P0 |

**Operations workflow:** View break queue → inspect original internal/external records and as-of date → launch supervised investigation → agent gathers evidence → proposes structured classification/correction/escalation → system validates evidence+policy → possibly reviewer approves matching action hash → commit or deny → verify result → close only on success or remain open/escalated.

**Validator workflow:** Pick model/prompt/policy/scenario batch → run experiments → inspect pass/fail rates and uncertainty → replay any failure against alternative controls → review evidence receipts and domain-state differences → decide **test-limited recommendation** (approve / conditional / reject) with stated conditions and limitations.

**Platform engineer workflow:** Trace run ID across LangGraph/gateway/ledger/outbox/Kafka/supervisor → inspect policy denies, retry/idempotency outcomes, consumer lag, p95/p99 latencies and service faults → confirm recovered state.

