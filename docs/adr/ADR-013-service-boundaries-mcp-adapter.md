# ADR-013: Java gateway as policy enforcement point + thin Python MCP adapter
Status: ACCEPTED (om ☑ kunal ☑, PR #11, 2026-10-29) · Resolves: U3 (part) · Spec: §7 §10 §11 §24 · ADR-002, ADR-005

## Context
§7 sends "authenticated MCP tool proposals" into a gateway that owns identity, OPA and budgets; the ledger re-checks sensitive conditions and is the only writer. MCP authorization changed across spec revisions (§24), so protocol churn should be isolated from enforcement. The team split puts everything below the tool boundary with Om.

## Options
- **A.** Java gateway with a REST tool API + a separate thin Python MCP adapter (official SDK).
- **B.** MCP server inside the Java gateway (Java MCP SDK / Spring AI): one hop fewer, but enforcement is coupled to that SDK's spec-revision support.
- **C.** Python gateway (FastAPI + MCP SDK): one process, but the enforcement stack splits across languages.

## Decision: A
- `services/gateway` (Spring Boot) is the policy enforcement point. `POST /v1/runs` issues short-lived Ed25519 run tokens; `POST /v1/runs/{runId}/tools/{tool}` = token → schema → budget/halt → OPA → ledger (gateway service JWT) → typed result; every decision is persisted.
- `services/mcp-adapter` (Python, official MCP SDK; pinned: Python SDK `mcp==2.3.0`, spec revision `2026-07-28` (both current on 2026-10-29, SH-02 C8; OM-06 re-verifies against the version it actually tests and bumps this line if it differs)) exposes exactly the §10 tools over Streamable HTTP and forwards each call with the agent's bearer token + traceparent. It holds no credentials, state or policy, so bypassing it gains nothing.
- The ledger trusts only the gateway service identity on `/internal`; `/admin` (operator) and `/review` (humans) are separate realms; agent tokens are rejected by the ledger (T-SEC-01).
- The rules baseline and the LLM both go adapter → gateway: identical evidence/access boundary (REQ-003).
- Om owns gateway + adapter including tool descriptions; Kunal approves description changes because they shape agent behavior.

## Consequences
- \+ Enforcement testable over plain HTTP (MockMvc, k6); MCP churn contained in one small service; T-SEC-01 is meaningful.
- − One extra local hop. It exists in every condition and sits outside the `gateway.onpath` span, so it does not bias H2.
- − Om works in two languages (Java + a small Python service).

## Verification
MCP Inspector lists exactly the §10 tools; the adapter container has no route to Postgres/OPA/Redis; T-SEC-01 and T-SEC-02 pass.
- The gateway takes run_id from the bearer token; a tool body whose run_id differs gets PERMISSION_DENIED (contract test + OM-05 negative test).
