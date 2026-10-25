## 0. INSTRUCTIONS FOR AI ASSISTANTS / FUTURE CONTRIBUTORS

- Treat this document as the **canonical intent and design**, not evidence that components exist. Ask for repository/branch/status if implementation decisions depend on actual progress; never invent completed tests, metrics, deployment, access permissions or results.
- Keep domain, security, evaluation and build decisions consistent with this specification. Cite its section IDs in designs/PRs. Use the requirement IDs `REQ-*`, test IDs `T-*`, and milestone IDs `M-*` for traceability.
- Preserve the original H1–H3 decision rules as preregistered; label all modifications **AMENDMENT** with date, rationale, and pre/post-specification results. Separate exploratory work from confirmatory results.
- Optimize for a **working, correct, reproducible two-person course project**. Prioritize P0 > P1 > P2. Do not invent microservices, vendor dependencies or model frameworks without an explicit requirement and measured benefit.
- Keep all simulations synthetic; do not integrate with real brokerage/bank accounts, issue live settlement instructions or post real money. All positions, trades, institutions and communications are fictional/synthetic or permitted public reference data.
- **Architecture rule:** LLMs propose; authenticated deterministic code authorizes and validates; only the ledger changes financial state; independent grading determines correctness; asynchronous monitoring cannot undo a prior commit.
- When generating implementation artifacts, output file paths, contracts, acceptance tests, setup instructions, assumptions and tradeoffs. Do not label a feature complete without executable evidence. If conflicts remain, log them in `§25 Decision Register`.
- Any industry/regulatory statements are context, not proof of regulatory certification or employer endorsement. No bank, FINOS, OCC or other body has approved this prototype.

