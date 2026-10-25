## 3. PROBLEM DEFINITION AND PRODUCT BOUNDARIES

**Reconciliation break:** A discrepancy among trade, position, cash or settlement records in the bank's internal books and external custodian/counterparty evidence. Resolution may be a justified correction, timing classification, verified cancellation, application of a corporate action or human escalation. Closing every open break is **not** equivalent to correctness; for some break types, **leaving open and escalating** is the right outcome.

**Failure families:** (F1) reward/proxy hacking via suspense plugs and unsupported closures; (F2) unauthorized writes including reference-data tampering; (F3) valid arithmetic but economically false postings; (F4) prompt-injected or fabricated supporting evidence; (F5) individually permitted actions producing invalid sequences; (F6) stale approvals/data and concurrency races; (F7) duplicate/reordered/delayed events; (F8) wrong escalation or misplaced confidence; (F9) control bypass, credential overreach or event/audit tampering; (F10) data-generator shortcut leakage / invalid benchmark claims.

**In scope (course):** Single simulated bank; cash equities and related settlement/positions; eight labeled break categories; read and constrained write tool calls; deterministic rule baseline; an LLM agent; prevention+monitoring; human maker-checker when appropriate; reproducible evaluation, replay, evidence and a compact review experience.

**Out of scope (course):** Real institution datasets/PII, production banking integration, real trading, real money, reconciliation of complex derivatives, model fine-tuning, general multi-agent systems, full onboarding workflow, speculative multi-domain expansion, enterprise-wide certification, Kubernetes, blockchain and complex stream processors/schema registries absent demonstrated need.

**Constraints:** Two engineers; Module 7 final delivery from original plan; public/synthetic data only; model usage limits/cost; university Explorer/vLLM potentially queued/unavailable; Docker Compose for deterministic local infrastructure; commercial model API for limited comparative arm; demonstration should not rely on live cluster queues.

**Landscape comparison from submitted research (descriptive, not a claim of exclusivity):**

| Existing system / work | What it illustrates | Second-Line-specific value still to prove |
|---|---|---|
| Smartstream Smart Reconciliations Premium | Commercial agentic exception handling, action logging, MCP in Sep 2026 announcement | Independent reproduction and evidence-grounded risk tests |
| Duco | Rule-based and agentic exception management with human oversight | Explicit independent oracle and adversarial financial-state tests |
| Goldman Sachs / Anthropic reported agents | Financial operational AI and trade-accounting focus | No access to or claim about their internal validation approach |
| BloombergGPT | Finance-domain language capabilities | Correct state-changing tool use, not only text tasks |
| τ-bench | **Already grades final database state against an annotated target** and reports all-k reliability | Finance-specific accounting invariants, evidence-bound ledger actions and safe escalation |
| AgentDojo / InjecAgent | Agent tool prompt-injection tests | Finance-specific wrong-but-balanced state and action-sequence risks |
| NeMo Guardrails / CaMeL | Conversation and architecture-oriented guardrails | Server-enforced ledger transaction integrity and truth-based scoring |
| FINOS AIGF / NIST RMF | Governance risk catalogs and assurance vocabulary | Executable test, trace, receipt and benchmark evidence |
| General LLM observability/evaluation tooling | Tool traces, agent trajectories and outcome assessment | Independent causal finance simulator and verifiable ledger-state difference |

**Novelty boundary:** τ-bench already evaluates final database state: therefore **do not claim that Second-Line invented state-based agent evaluation**. Do not claim others never assess agent tool use or business outcomes. The particular contribution is a finance-grounded composition with rigorous experimental evidence, not invention of the underlying platform primitives.

