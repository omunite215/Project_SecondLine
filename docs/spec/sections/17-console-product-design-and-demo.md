## 17. CONSOLE / PRODUCT DESIGN AND DEMO

**Information architecture (minimum):**

- `Operations / Break Queue`: filters by status, break type, severity, scenario as-of; show internal vs custodian evidence; risk and approval status; exact action proposed vs actual ledger delta; escalation queue.
- `Risk / Model Validation`: model/prompt/policy/config selection, cohort runs, hypothesis tests, confidence intervals, error taxonomy, safe automation coverage vs false-resolution rate, explain which tests failed.
- `Counterfactual Lab`: choose scenario/run, pick deterministic action replay vs paired live LLM, select control versions, run in isolated reset snapshots; side-by-side timelines and verified financial **state differences**. No synthetic illustrative number presented as real result.
- `Engineering / Trace Explorer`: correlation by run/action/transaction IDs; MCP calls, gateway/OPA decision, approval, Spring/Postgres commit, outbox/Kafka, monitor and receipt verification; p95/p99 and lag; retry/chaos incidents.
- `Evidence Export`: immutable test manifest, signed/checksummed receipts, aggregate results, limitations, model/dataset card, approval recommendation with scope; append audit verification status.

**Interaction patterns:** Role-aware access; explicit action previews with evidence references and source versions; maker/checker separated; approvals require a reason code (and ideally acknowledgement of the actual state delta); user-visible error explanations; clear labels `SIMULATED`, `SCRIPTED POC`, `REAL LLM RUN`, `HYPOTHETICAL` and `EXPLORATORY` as applicable. WebSockets/SSE for updates with polling fallback; show audit provenance rather than generated reasoning as proof.

**5–7-minute demo script (live path):**

1. **0:00–0:45** Explain business problem: 1,000 vs 900 shares may be partial settlement, timing or wrong internal booking; over-automation can hide risk.
2. **0:45–1:45** Load one synthetic case and its independently generated evidence, show rule baseline and explain why free text is relevant.
3. **1:45–2:45** Execute a real agent in isolated **controls-off** run; show actions, misleading proxy if it happens (do not force a desired outcome with post-hoc editing). A pre-recorded *labeled replay* is an acceptable reliable backup if live inference is uncertain.
4. **2:45–4:15** Replay original proposed action sequence with full controls OR run a matched live controlled trial; be explicit which. Show OPA decision, financial pre-commit validation, evidence references, optional maker-checker, exact ledger commit/denial.
5. **4:15–5:30** Inspect end-state diff, final verified outcome, rejected attempts, escrow/suspense behavior and reasons for escalation. Explain kill switch cannot retroactively undo committed damage.
6. **5:30–6:30** Display an existing aggregate evaluation with CI, real vs rules baseline, model and policy versions, trace/audit verifier, limited validation decision.
7. **6:30–7:00** State measured limitations and architectural tradeoffs; invite reviewer to run local smoke suite.

**Demo reliability:** Prewarm model endpoint if available, seed 1–3 strong test cases, use deterministic data fixture/reset, scripts `make demo-up`, `make demo-seed`, `make demo-run`, `make demo-test` (names illustrative), recorded *clearly labeled* fallback, no reliance on Slurm queue. Include one **successful legitimate action** and one rejected or escalated unsafe/unsupported proposal. Full system can be more extensive than a live demo environment.

