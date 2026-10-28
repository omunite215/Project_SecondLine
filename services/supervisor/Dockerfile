# syntax=docker/dockerfile:1
# KG-01 · sl-supervisor image. Multi-arch (arm64 Kunal, amd64 Om/CI); pinned tags only (infra/CLAUDE.md).
# Build from the repo root: docker build -f services/supervisor/Dockerfile .
FROM python:3.12.13-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/.venv PATH=/app/.venv/bin:$PATH
WORKDIR /src
# Workspace metadata for every member (uv needs it to read uv.lock); source only for what this image runs.
# Never copy factory/evaluation source here: hidden truth stays out of unprivileged images (golden rule 4).
COPY pyproject.toml uv.lock .python-version ./
COPY packages/scenario-factory/pyproject.toml packages/scenario-factory/
COPY packages/evaluation/pyproject.toml packages/evaluation/
COPY packages/audit-verifier/pyproject.toml packages/audit-verifier/
COPY services/agent/pyproject.toml services/agent/
COPY services/supervisor/pyproject.toml services/supervisor/
COPY services/mcp-adapter/pyproject.toml services/mcp-adapter/
COPY packages/contracts/py packages/contracts/py
COPY services/supervisor services/supervisor
RUN uv sync --frozen --no-dev --package sl-supervisor --no-editable && rm -rf /src
RUN useradd --system --uid 10001 app
USER app
WORKDIR /app
# Placeholder until the service has an entrypoint (KG-08 agent, KG-11 supervisor).
CMD ["python", "-c", "import sl_supervisor"]
