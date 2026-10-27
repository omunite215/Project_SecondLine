# apps/console — review console (owner: Om)
Next.js (App Router) · TypeScript strict · pnpm · Playwright. Never a security boundary: every rule is enforced server-side.
Routes: /breaks (ops queue) · /approvals (checker inbox) · /runs/[id] (trace timeline) · /lab (counterfactual) · /validation · /export
`lib/api/` = typed clients generated from packages/contracts/openapi (review.yaml, eval.yaml) — never hand-write API types.
Commands: `make test-console` · `pnpm --dir apps/console dev`
- Label provenance on every number and timeline: SIMULATED · SCRIPTED · REAL LLM RUN · HYPOTHETICAL · EXPLORATORY.
- Approval screen: evidence refs + versions, proposed vs resulting delta, digest; reason code mandatory.
- Never render truth/oracle data before grading; eval data only via the eval API.
- Accessibility: keyboard navigation, visible focus, explicit error states (NFR-12).
- OM-21/22 require the frontend-design skill; T-UI-01 uses Playwright (VS Code extension recommended in .vscode/extensions.json).
