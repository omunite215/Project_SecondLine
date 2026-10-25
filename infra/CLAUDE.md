# infra — local platform (owner: Om · infra/hpc owner: Kunal)
compose/ (profiles core · app · events · obs · ui · chaos) · db/init/ (roles, schemas) · opa/ (policies + tests) · observability/ (otel, prometheus, grafana) · toxiproxy/ · k6/ · hpc/ (vLLM sbatch)
Commands: `make up PROFILES="core app"` · `make down` · `make ps` · `make logs SVC=ledger TAIL=50`
- Multi-arch images only (Kunal = arm64, Om/CI = amd64); pin tags, never `:latest`.
- Every service: healthcheck + mem_limit sized for Om's 16 GB host; JVMs -Xmx512m.
- No Kubernetes (ADR-009). No secrets in compose files: env files live outside git.
- Ollama runs natively on the host (Mac Metal / WSL CUDA); containers reach it at host.docker.internal:11434.
- .github/ (CI/CD, rulesets, workflows) is owned by Om; required checks grow with OM-25.
