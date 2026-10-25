## 20. DELIVERY PLAN — PRESERVE MODULES, PRIORITIZE VERTICAL SLICES

**Original (submitted) module commitments:**

| Module | Original activities | Exit criterion |
|---|---|---|
| 4 | Java ledger/outbox, MCP tools, LangGraph agent, generator, Docker Compose, 40-dev + 20 pilot | Actual end-to-end agent resolves/escalates break; POC tests pass on full ledger |
| 5 | OPA, Redis, Kafka relay, invariant monitors, hash-chain audit, Explorer vLLM, baseline cases | Seeded violations blocked/detected, chain verifies |
| 6 | React/WebSocket review console, versioned API, observability, load; 3,000 open + 300 frontier runs | H1–H3 analyzed with CIs |
| 7 | Hardening, final live demo, datasheet, model cards, governance mapping, paper/report | Working system demonstrated, research report submitted |

**ADOPTED recommended implementation milestones (may overlap modules):**

| Milestone | Priority | Work products | Exit / stop rule |
|---|---|---|---|
| M-0 Define contracts | P0 | Domain schema, tool JSON schemas, truth isolation, success metric denominators, repo skeleton, ADRs | Interfaces frozen for vertical slice |
| M-1 Truthful simulator | P0 | Spring/Postgres journal, causal B1–B8 factory, snapshots, grader, rules baseline | Golden cases/property tests and false-balanced test pass |
| M-2 Real agent | P0 | LangGraph/MCP, structured proposals, API/model, end-to-end traces | Agent handles complete real inference case in isolation |
| M-3 Safety boundary | P0/P1 | OPA scope, reviewer approval, DB idempotency, pre-commit evidence checks, outbox, monitors | Bypass/duplicate/bad-action tests pass; no dirty state |
| M-4 Science & replay | P1 | Scored frozen experiment, clustered statistics, action and live paired replay, blind tests | H1–H3 tested without false claims; meaningful state diff |
| M-5 Product & hardening | P2 | Console, validation evidence, observability, k6/chaos, 5–7-minute demo and docs | Independent reviewer can run demo and inspect artifact |

**Cut order if schedule slips:** Defer fancy console views and full load scale first, then advanced cryptographic anchors and broad chaos catalogue, then commercial-model expansion; **protect correct financial model, real tool-using LLM, pre-commit safety, independent grading, core 3-condition experiment and honest evidence**. Disclose any inability to meet submitted 3,300-run commitment rather than implying completed runs. Keep minimal reviewer UI where feasible; recorded traces are backup only, not substitute for actual final system.

**Dependencies:** Do not build replay/UI against non-versioned APIs; contract and scenario truth first. Do not tune on held-out test cases. Do not consider policy alone sufficient without ledger transaction check. Run an end-to-end vertical slice early to avoid two independent subsystems that connect only near submission.

