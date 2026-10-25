---
paths:
  - "services/agent/**"
  - "services/mcp-adapter/**"
  - "services/gateway/**"
  - "services/ledger/**"
  - "services/supervisor/**"
  - "apps/console/**"
  - "packages/scenario-factory/**"
---
# Hidden-truth isolation (REQ-006, T-DOM-03, ADR-015)
- Only packages/scenario-factory (writes) and packages/evaluation (reads) touch Truth documents, `truth/` dirs, `truth_ref` and `SLCANARY-` canaries.
- agent, mcp-adapter, gateway, ledger, supervisor and console must not import `sl_factory.truth` / `sl_eval.grader`, mount `data/generated/*/truth`, or expose truth fields (root_cause, allowed/forbidden_outcomes, expected_state_delta, required_evidence_ids, explanation).
- Visible records show symptoms (internal 1000 vs custodian 900), never root causes; ids are opaque (no "B7", "dup", "shortfall" in agent-visible fields).
- The ledger loader rejects bundles that contain any Truth-schema field.
- A PreToolUse hook blocks obvious violations; the CI leakage scan (KG-05) is the real gate. If the hook blocks wrongly, tell the human.
