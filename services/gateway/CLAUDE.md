# services/gateway — policy enforcement point (owner: Om)
Spring Boot · Java 21. Stateless except Redis. Each tool call: token → schema → budget/halt → OPA → ledger → typed result. Never mutates financial state itself (ADR-013).

## Planned layout
```text
com.secondline.gateway
  runs/      POST /v1/runs → ns-bound run + short-lived Ed25519 JWT
  tools/     POST /v1/runs/{runId}/tools/{tool}; one handler per §10 tool
  auth/      token verification (aud, exp, run_id, ns, allowed_tools, controls)
  policy/    OPA client (decision + bundle hash); writes fail closed
  budget/    Redis counters + halt flags (advisory; durable status lives in the ledger)
  routing/   ledger client with the gateway service JWT; propagates traceparent
  observe/   Micrometer `gateway.onpath` histogram + OTel spans
```
## Commands
`make test-gateway` · `make test-sec` · `./gradlew :services:gateway:bootRun`
## Conventions
- The control condition (off | monitor | full) comes from the run record, never from the request (ADR-014).
- `gateway.onpath` = request received → response sent. It is the H2 latency source: don't move its boundaries without SH-06 sign-off.
- Denied ⇒ decision persisted + DENY receipt; zero ledger mutation.
- Read first: §8 §10 §11 shards; ADR-013/014.
