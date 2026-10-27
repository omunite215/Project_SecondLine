## 10. TOOL CATALOG AND LLM WORKFLOW

**Agent-readable tools (MCP, versioned, schema-validated):**

| Tool | Default privilege | Meaning / guard |
|---|---|---|
| `list_breaks` / `get_break` | Read, run-scoped | Selected break, status, identifiers, cutoff, case metadata |
| `read_trade`, `read_bookings`, `read_positions` | Read | Internal booked/traded state with as-of version |
| `read_custodian_statement`, `read_settlement_status` | Read | External synthetic evidence and report provenance |
| `read_reference_data`, `read_corporate_actions`, `read_fx_snapshot` | Read | Versioned SSI/LEI/rates/events; no write privileges |
| `read_evidence` | Read | Text memos / synthetic counterparty emails / supporting documents, **untrusted content** |
| `request_counterparty_clarification` | Simulated messaging only | Appends synthetic communication; response generated from canonical world, never real email |
| `propose_classification` | Restricted write | Status with evidence and allowed reason; not automatic arbitrary closure |
| `propose_booking_correction` / `propose_corporate_action` | High-risk write | Pre-commit validator; type-specific state delta; approval as needed |
| `propose_adjustment` | High-risk financial write | Explicit currency, amount, account, affected trade, purpose, versions; no arbitrary SQL |
| `escalate_break` | Restricted write | Human queue with reason, cited evidence, status retained accurately |
| `get_action_status`, `get_approval_status` | Read | Idempotent inspect/poll; not extra unauthorized writes |

**Explicitly NOT agent-exposed:** unrestricted `UPDATE` SQL, direct journal edit, reference-data modification, arbitrary account creation, hidden scenario oracle, raw Kafka publishing, approval forgery, full filesystem/network access, unlimited counterparty messaging, developer/debug bypass tools.

**Agent design:** LangGraph state machine: `START → retrieve case → reconcile facts → evaluate evidence sufficiency → choose classify/correct/escalate → request gateway tool → (approval pause | denial branch | commit) → verify observed result → finalize with evidence & uncertainty`. Put explicit max tool calls/time/cost, bounded iterations, checkpoint/resume by run ID, cancellation and forbidden escalation loops. Use deterministic structured outputs via Pydantic/JSON schema; record schema version and validation errors. If a tool denies an action, model must not reinterpret denial as permission.

**Prompt policy:** System prompt specifies role, allowed methods, objective **maximize independently correct outcomes not raw closure**, evidence requirements, abstention/escalation when uncertain, noncompliance with instructions inside tool/evidence text, no financial authority without server gate; tool descriptions must be precise. Few-shot examples of correct resolution *and* safe escalation are allowed only from dev split; no evaluation content leakage. Prompt versions/hashes in every run manifest. Minimize hidden chain-of-thought retention; store structured plan/action justification rather than relying on introspective claims.

**Comparison strategies:** (A) deterministic rules engine; (B) real LLM with controls off in disposable isolated ledger; (C) real LLM with async monitors and kill switch only; (D) same LLM with full OPA/pre-commit/idempotency/monitor controls. Original preregistered statistical experiment compares B/C/D; rules engine A is a **new extension**. Independent models: one open-weight served by vLLM on Explorer if available, one frontier provider arm on smaller subset. Freeze exact model IDs and inference settings per campaign; don't assume a model is deterministic merely because temperature is zero. Track actual context tokens, tool calls, cost and retries.

