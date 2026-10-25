# services/mcp-adapter — MCP tool surface (owner: Om · descriptions reviewed by Kunal)
Python · official MCP SDK (version + spec revision pinned in ADR-013) · Streamable HTTP. Thin and unprivileged: no DB, OPA, Redis or secrets.
```text
src/sl_mcp/server.py    transport; passes Authorization bearer + traceparent through
src/sl_mcp/tools.py     tool registry generated from packages/contracts/tools/*.schema.json
src/sl_mcp/forward.py   httpx → gateway POST /v1/runs/{runId}/tools/{tool}
descriptions/<tool>.md  LLM-facing text: precise, no policy hints, no truth
```
Commands: `make test-mcp` · `uv run --package sl-mcp python -m sl_mcp.server`
- Exactly the §10 catalog; nothing from the NOT-exposed list.
- Evidence text only in `untrusted_text` fields, never echoed into descriptions or error messages.
- A description change alters agent behavior → Kunal approves the PR; note it in docs/team/handoffs/.
- OM-06 requires the mcp-server-dev skill (gate-checked when the card starts) — follow its server patterns.
