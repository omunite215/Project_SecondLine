# Handoff: Kunal → Om · SH-02 Kunal's half (scenario, truth, attacks, eval API)
Branch `kunal/SH-02-scenario-truth` (built on `om/SH-02-contracts-v1`) · §5 §9 §14 §15 · ADR-015, ADR-016 · T-DOM-03, REQ-004/005/007

## What changed
- `packages/contracts/VERSION` stays **1.0.0** (no `contracts-*` tag exists yet; these are additions before the v1 tag).
- New schemas: `scenario/manifest` (agent-visible: ids, hashes, refs only), `scenario/run_manifest` (**x-privileged**, the full §9 set), `scenario/world_bundle` (what the ledger loads), `scenario/ns_export` (ADR-015 state hash input), `scenario/truth` (**x-privileged**), `attacks/attack_pack` (**x-privileged**), `openapi/eval.yaml` skeleton.
- **Touches your files:** `reason_code` moved from `actions/proposed_action.schema.json` to `common.schema.json#/$defs/reason_code` (enum identical, C4, which I confirm); new `$defs/break_type` (B1–B8, privileged). One assertion in `tests/kit/test_sh_02_shapes.py` now follows the `$ref`.
- **C6 confirmed** (digest excludes `agent_explanation`).
- **§9 deviation:** `break_type`, `seed`, `split`, `pressure_level`, `injection_condition` and `truth_ref` are only in `run_manifest`, because break_type is a root-cause label and seed regenerates truth (golden rule 4).

## How to use it now
- `make contracts-check` → `contracts OK`; `python3 -m unittest tests/kit/test_sh_02_scenario.py` → 13 OK.
- Ledger loader (OM-03/OM-08): validate the bundle against `scenario/world_bundle.schema.json` and reject on failure. The schema already rejects truth-named evidence keys, B1–B8 labels as keys and `SLCANARY-` in free text. It does **not** check per-currency balance (I1) or ISO 4217 minor units; those stay in your validators.
- Example: `packages/contracts/examples/scenario/world_bundle_minimal.json` (B3, 1 USD trade, 0.01 nostro difference) and `ns_export_minimal.json`.
- Eval API errors: `PERMISSION_DENIED` (unknown or not-yours run, fail closed), `STATE_CONFLICT` (not graded yet), `IDEMPOTENCY_CONFLICT`, `RUN_HALTED`. `ORACLE_MISMATCH` never appears.

## Breaking?
- Not against main (nothing tagged). Against your branch: only the `reason_code` `$ref` move. Codegen type names may change once `make codegen-py` lands (KG-01 #14).
- Examples added: `examples/scenario/*` (7), `examples/attacks/attack_pack_dev.json`, and 16 rejected cases in `examples/invalid/{manifest,run_manifest,world_bundle,ns_export,truth,attack_pack}_*.json`.

## What I need back (before the contracts-v1.0.0 tag, SH-02)
1. Approve or adjust the `reason_code` move into common and the runner-only manifest.
2. **B3 accounting direction** (SH-03 / ADR-016 #10): `truth_b3.json` books 4100 vs 1300 per the table, but the break shows in nostro 1110. Which accounts does a B3 adjustment hit?
3. ADR-013 C8 pin and ADR-015 → ACCEPTED in #11; you tag after merge.
4. Fine with the evidence-key denylist also blocking `cause` and `expected_*`? (The factory, KG-03/04, will avoid those names.)
