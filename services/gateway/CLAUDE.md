# services/gateway — policy enforcement point (owner: Om)
Spring Boot · Java 21. Stateless except Redis. Each tool call: token → schema → budget/halt → OPA → ledger → typed result. Never mutates financial state itself (ADR-013).

## Layout (OM-05; [Om] = Om writes it, learn card)
```text
com.secondline.gateway
  token/     RunTokens [Om] (Ed25519 run JWTs, G2/G3), SigningKeys (JWK file, missing → no start), KeyGen
  pipeline/  ToolPipeline.handle [Om] (stage order, conditions, fail-closed mapping); ToolCall/ToolResult/Stage
  web/       ToolController (strict JSON object bodies), RunController, ErrorAdvice (contract errors only)
  runs/      RunService: POST /v1/runs, operator token, Idempotency-Key, ledger registers the run first
  route/     ToolRoutes: every INDEX.json tool → READ | ACTION | SIMULATED | UNROUTED (parity-tested vs ledger-internal.yaml)
  client/    LedgerClient (service JWT, 4xx pass-through only for contract errors), PolicyClient (OPA, 200 ms), DecisionLog
  guard/     RunGuard / InMemoryRunGuard: call budget, halt, C_msg (OM-12 replaces with ledger-backed flags)
  schema/    InputSchemas: DOMAIN_INVALID that never echoes input
  observe/   OnPathFilter: `gateway.onpath` timer (SLO buckets 1–500 ms; tool ∈ §10 or "unknown"; status)
  config/    GatewayConfig wiring; gateway.* properties in application.yml
```
## Commands
`make test-gateway` · `make test-sec` · `./gradlew :services:gateway:bootRun`
## Conventions
- The control condition (off | monitor | full) comes from the run record, never from the request (ADR-014).
- Spans carry run_id (path) and action_id (only if UUID-shaped); never tokens, keys or free text.
- `gateway.onpath` = request received → response sent. It is the H2 latency source: don't move its boundaries without SH-06 sign-off.
- Denied ⇒ decision persisted + DENY receipt; zero ledger mutation.
- Read first: §8 §10 §11 shards; ADR-013/014.
