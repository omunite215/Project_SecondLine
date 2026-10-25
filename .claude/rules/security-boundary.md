---
paths:
  - "services/gateway/**"
  - "services/mcp-adapter/**"
  - "services/ledger/**/security/**"
  - "services/ledger/**/api/**"
  - "infra/opa/**"
---
# Security boundary (§8, §11, ADR-013, ADR-014)
- Default deny. Every sensitive call re-verifies the token server-side (aud, exp, run_id, ns, allowed tools).
- The gateway never authorizes from client-supplied fields; the ledger re-checks sensitive conditions (downstream recheck).
- Denied ⇒ zero mutation + a DENY receipt; log every decision with the policy bundle hash.
- Redis is advisory; durable run status in Postgres is authoritative at commit time.
- The MCP adapter holds no credentials, state or policy; it only forwards.
- Secrets come from env/secret files outside the repo; redact Authorization headers, tokens and keys from logs and spans.
- OPA 1.x = Rego v1 syntax (`if`, `contains`); every rule ships with `opa test` cases incl. default-deny.
