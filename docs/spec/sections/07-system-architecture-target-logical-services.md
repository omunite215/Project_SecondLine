## 7. SYSTEM ARCHITECTURE — TARGET LOGICAL SERVICES

```text
                   +-------------------------------+
                   | React/Next.js Review Console  |
                   | ops | risk | replay | traces  |
                   +---------------+---------------+
                                   | API/SSE or WebSocket
   Commercial model API            v
   OR vLLM (Explorer/optional)  [Run/Review API]
               ^                    ^
               |                    |
     +---------+--------------------+-------+
     | LangGraph runner + scenario/eval     |
     | agent state, tools, manifests         |
     +------------------+--------------------+
                        | authenticated MCP tool proposals
                        v
            [Gateway: identity + OPA + budgets]
                        | permit / deny / wait approval
                        v
             [Ledger: pre-commit verifier]
             finance constraints + evidence/version checks
                        | atomic domain mutation
                        v
             [Spring Boot + PostgreSQL]
              journal | state | outbox | approvals
                        | outbox relay (at least once)
                        v
                     [Kafka]
                        |
            +-----------+-------------+
            |                         |
    [Async financial monitors]   [Audit/trace consumer]
            |                         |
      alarm / kill future       signed/hash-chained receipts
      calls; investigation      digest anchors (P2)
            +------------+------------+
                         |
                   Run/Review API

 Cross-cutting: OpenTelemetry/Prometheus/Grafana/Jaeger;
 reproducible scenario snapshots; independent truth grader;
 replay engine; rules baseline; persistent run manifests.
```

**Deployment:** Local Docker Compose for PostgreSQL, Kafka, Redis, OPA, API, gateway, agent, monitor and console as resource permits. Ledger/Spring and Python agent separate logical services; do not require *every* logical module to be a physical microservice. Use container healthchecks, migrations, deterministic fixture loading, bounded startup time and `make demo`/documented commands. vLLM open-weight option on Northeastern Explorer via Apptainer/Slurm (if granted); compare commercial API on stratified subset; local small-model or API demo fallback. No mandatory Kubernetes.

**Boundary ownership:** Only ledger can mutate financial state; only truth service/grader sees secret oracle labels; gateway owns external agent privileges; ledger enforces business safety even if gateway misconfigures; supervisor detects after commit and cannot roll back already completed mutations; API and UI do not bypass these rules. In controls-off scientific runs, financial writes occur **only in isolated, disposable synthetic environment**, never in shared production-like dataset.

**Why tools:** Spring Boot/Java for typed domain and atomic state; PostgreSQL for durable relational transactions; LangGraph for pause/resume deterministic orchestration; MCP for versioned model-agnostic tools; OPA/Rego for external reviewable authorization; Redis for fast ephemeral run budgets/kill flags (not sole financial authority); Kafka for replay/fan-out/async monitors; vLLM for open-weight inference; OpenTelemetry+Prometheus+Grafana+Jaeger for traces/metrics; pytest/Hypothesis, Testcontainers, k6 and Toxiproxy for correctness/integration/load/chaos; GitHub Actions for CI. Optional UI framework: Next.js+TypeScript+React; original React-only console remains compatible.

