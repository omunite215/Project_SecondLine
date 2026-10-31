# Handoff: Om → Kunal · contracts 2.0.0 for OM-04 (ledger reads, loader, export)
Branch `om/OM-04-contracts-2-0-0` · §5 §9 §10 §12 · ADR-015 (Amendment 1), ADR-019 · REQ-001 REQ-002 REQ-011 · T-EVAL-03 T-DOM-03

## What changed
- `VERSION` **2.0.0** (major), `$id` base `…/contracts/2/`. It skips 1.1.0, which #32 and #33 both claim: **merge #32 and #33 first**, and this branch rebases onto them.
- `openapi/ledger-internal.yaml`: one GET per §10 read tool under `/internal/v1/ns/{ns}/…`, returning the tool's output schema.
- `openapi/ledger-admin.yaml`: `POST /admin/v1/ns`, `POST …/{ns}:load`, `GET …/export`, `GET …/state-hash`, `DELETE …/{ns}` (retire) and `POST /admin/v1/runs`.
- **Your half:**
  - `scenario/world_bundle.schema.json`: `bundle_version` "2.0", plus required `institutions[]` and `counterparties[]`, and `trade.counterparty_id`.
  - `ns_export` description: the state hash excludes `ns`.
- `tools/read_settlement_status.output.schema.json`: the status enum is now the evidence enum.

## How to use it now
- Factory (KG-03): emit one institution and counterparty per broker, and set `counterparty_id` on every trade. Example: `examples/scenario/world_bundle_minimal.json` (`ins_0000G001` / `cpt_0000H001`).
- Grader (KG-06): state hash = `sha256(JCS(export minus "ns"))`. A Python test vector lands in `test-vectors/state_hash/` with OM-04 Task 5.
- Runner (KG-15): create the ns, then `:load` (the same bundle again → 200 no-op; a different one → 409 `IDEMPOTENCY_CONFLICT`), then `POST /admin/v1/runs` with `manifest_ref`.
- Unresolvable ids return 403 `PERMISSION_DENIED` from every ledger route, never 404.

## Breaking?
- Yes. 1.x bundles fail (`bundle_version`, missing counterparties), and `PARTIAL` is gone. No producer or consumer exists yet (KG-03 and OM-06 are todo), so the migration is the examples only. All 15 `world_bundle*` examples are updated.
- `libs/contracts-java` `ID_BASE` (#32) moves to `/contracts/2/` when this rebases.

## What I need back
1. Approve the WorldBundle changes (your shape) and ADR-015 Amendment 1 (tick `kunal ☐`).
2. Is one institution per counterparty enough for B8 (SSI), or do you want SSI records keyed by counterparty in the bundle now?
