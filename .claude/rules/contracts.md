---
paths:
  - "packages/contracts/**"
  - "libs/contracts-java/**"
---
# Contracts — shared, both owners approve
- JSON Schema 2020-12 with versioned `$id`; additive change = minor, breaking = major + migration note in the PR.
- After any change: bump VERSION → update examples/ + test-vectors/ → `make codegen` → `make contracts-check` → `/handoff`.
- Never hand-edit generated code (libs/contracts-java build output, packages/contracts/py/**/_generated).
- Error codes only from errors.json. ORACLE_MISMATCH is grader-only; runtime services never return it.
- Servers derive authority-bearing fields (e.g. requires_approval); client-supplied booleans are never trusted.
- LLM-facing tool descriptions live in services/mcp-adapter/descriptions/, not here; keep schema `description`s short.
