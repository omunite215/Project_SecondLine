# ADR-015: Run namespaces, snapshots and hidden-truth isolation
Status: PROPOSED (accept in SH-02) · Spec: §5 §7 §9 §12 (replay protections) · REQ-006, REQ-011, T-DOM-03, T-EVAL-03

## Decision (proposed)
- Every run executes in a fresh namespace `ns` (UUID). All ledger rows carry `ns`; keys are (ns, id); run tokens bind run → ns and the ledger checks token ns against path ns. Optional hardening: Postgres row-level security keyed on `app.ns`.
- Reset = a new ns loaded from the WorldBundle (no in-place rollback). Snapshot id = bundle sha256. State hash = sha256(JCS(canonical ns export)), verified after load and stored in the run manifest (T-EVAL-03).
- Truth stays in files under `data/generated/<split>/truth/`, readable only by grader/runner processes; never mounted into agent, mcp-adapter, gateway, ledger, supervisor or console containers. Each truth file carries a `SLCANARY-<hex>` canary that CI scans for (KG-05).
- The ledger loader rejects bundles containing any Truth-schema field. Visible ids are opaque; visible records show symptoms, not root causes.
- The console shows outcomes only via the eval API after grading.

## Alternatives
Per-run Postgres schema or template-database clone (stronger isolation, slower resets, heavy on a 16 GB laptop); a single namespace with truncate (no parallel runs, no 50-run k6 test).

## Consequences
Parallel runs on one Postgres; cheap deterministic resets; isolation relies on (ns, id) keys + tests (+ RLS if enabled).
