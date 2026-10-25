# services/agent — LangGraph agent + rules baseline (owner: Kunal)
Python 3.12 · LangGraph · langchain-mcp-adapters · Pydantic v2 (`sl_contracts`). Runs strategy A (rules) and the LLM under controls B/C/D.
```text
src/sl_agent/graph/        §10 state machine: retrieve → reconcile → sufficiency → choose → call_tool → approval | denial | commit → verify → finalize
src/sl_agent/toolclient/   ToolClient interface: MCP backend (real) + fake backend (tests)
src/sl_agent/llm/          OpenAI-compatible client (Ollama / vLLM) + provider SDKs; settings recorded
src/sl_agent/strategies/   llm/ and rules/ behind the same ToolClient surface
src/sl_agent/prompts/      system + L0–L3 pressure templates; dev-split few-shots only; hashed
src/sl_agent/budgets.py    max tool calls / time / tokens; no escalation loops
```
Commands: `make test-agent` · `make run-one SCN=<dev id> CONTROLS=off STRATEGY=llm`
- A denial is information, never permission; never retry a denied write with cosmetic changes.
- Store a structured plan + justification, not hidden chain-of-thought.
- Local model: `OPENAI_BASE_URL=http://localhost:11434/v1` natively; containers use host.docker.internal.
- Read first: §10 §13 §14 shards; ADR-014; .claude/rules/experiment-integrity.md for anything in prompts/.
- LangGraph skills (langgraph-fundamentals, langgraph-persistence) live in services/agent/.claude/skills/ — vendored by `make skills-install`, pinned in tooling/skills.lock.json, gitignored — and load only when Claude works here. Prefer them over memory for StateGraph, checkpointers and interrupts.
