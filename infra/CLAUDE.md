# infra — local platform (owner: Om · infra/hpc owner: Kunal)
compose/docker-compose.yml (profiles core · app · events · obs · ui · chaos) · db/init/ (schemas + roles) · observability/ (otel, prometheus) · toxiproxy/ · opa/ (policies, later) · k6/ (later) · hpc/ (vLLM sbatch)

Commands: `make bootstrap` (once: .env with random secrets, pre-commit hook; no JDK needed) · `make up PROFILES="core app"` (waits for healthy, 120 s cap) · `make down` · `make ps` · `make logs SVC=ledger TAIL=50` · `make db-shell` · `make lint` · DB-role tests: `python3 -m unittest discover -s tests/infra` (needs core up)

| profile | services | mem_limit |
|---|---|---|
| core | postgres 17, redis 7, opa 1.x | 768 MB total (512/128/128) |
| app | ledger :8081, gateway :8080 (mcp-adapter: OM-06) | 768 MB each, JVM -Xmx512m |
| events | kafka 4 KRaft (supervisor: KG cards) | 1 GB |
| obs | otel-collector, jaeger :16686, prometheus :9090, grafana :3000 | 256 MB each |
| ui | console (OM-21) | — |
| chaos | toxiproxy :8474 (postgres → :15432, redis → :16379) | 64 MB |

- DB: schemas `ledger` (owned by ledger_app), `audit` (ledger INSERT + SELECT only), `eval` (truth; only grader_ro reads). Login users `ledger_svc`, `grader_svc`, `operator_svc`. Roles live in db/init and run only on an empty volume: after editing them, `docker compose -f infra/compose/docker-compose.yml --env-file .env --profile core down -v`.
- Multi-arch images only (Kunal = arm64, Om/CI = amd64); pin exact tags, never `:latest`. Every service: healthcheck + mem_limit; host ports bind to 127.0.0.1. `tests/kit/test_om_01_compose.py` enforces all of this.
- Om's laptop: check `free -g` before stacking profiles (WSL reported 5 GB on 2026-10-28). Default "core app"; never obs + events + ui alongside Gradle runs. CI's `stack` job starts every profile.
- Distroless images (opa, otel-collector) have no shell: their healthcheck only proves the process is up; readiness is checked from the host (tests/infra, CI).
- No Kubernetes (ADR-009). No secrets in compose files: values only as `${VAR:?}` from `.env` (gitignored, `make bootstrap`).
- Ollama runs natively on the host (Mac Metal / WSL CUDA); containers reach it at host.docker.internal:11434.
- .github/ (CI/CD, rulesets, workflows) is owned by Om; required checks: docs/setup/GITHUB.md.
