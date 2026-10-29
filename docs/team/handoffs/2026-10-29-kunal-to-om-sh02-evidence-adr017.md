# Handoff: Kunal → Om · SH-02 evidence contract aligned to ADR-017 (2026-10-29)
Task: SH-02 (Kunal's half, follow-up to the #11 leakage audit) · ADR-017 (PROPOSED on main; Om approved on #16) · T-DOM-03 T-DOM-04 REQ-006

## What changed (contracts VERSION stays 1.0.0: #11 merged, but `contracts-v1.0.0` isn't tagged yet)
- `common.schema.json`:
  - `evidence_kind` is now ADR-017's closed set, adding `INTERNAL_BOOKING` and `SETTLEMENT_STATUS`.
  - New `evidence_record_kind` = every kind but `INTERNAL_BOOKING`.
  - `opaque_id` rejects dev/eval/blind/test in any case, the same `not` that `scenario_ref` has.
- `scenario/world_bundle.schema.json`:
  - Evidence `kind` → `evidence_record_kind`.
  - `fields` keys are **allowlisted per kind**, which replaces the exact-name blocklist that let `root_cause_hint` through.
  - Values are **typed per key**: decimals, dates, ISIN, currency, `opaque_id`, and enums for `side` and `status`. `status_code` and `event_type` are 4-letter ISO codes; KG-02 cites the lists.
  - `source_system` gets the split guard.
- `tools/read_evidence.output.schema.json` (your area, one line): `kind` → `evidence_record_kind`. read_evidence returns bundle records, never bookings.
- `tests/kit/test_sh_02_tools.py` (your test, one line): the one-source assertion now points at `evidence_record_kind`.

## How to use it now
An INTERNAL_BOOKING citation is a plain `evidence_ref`: `{"record_id": "trd_0000B001", "version": <read_trade.record_version>}`, or an `entry_id` with `read_bookings.record_version`. OM-08 resolves the ID against ledger tables, not the evidence store.

## Breaking?
- No released consumer yet.
- Every `opaque_id` generator (ledger, gateway, factory) must **re-draw on a split-word hit, identically in every split**, so the ID distribution doesn't reveal the split.
- Examples: `examples/scenario/world_bundle_minimal.json` gains a SETTLEMENT_STATUS record, plus 7 new `examples/invalid/world_bundle_*` cases. `test_sh_02_evidence.py` checks that each one fails at its intended path.

## What I need back
1. **Movements gap (ADR-017):** ADR-017 says INTERNAL_BOOKING refs can point at movement IDs, but no tool exposes `movement_id` and a world-bundle `securities_movement` has no version. Should we expose movements (with `record_version`) in a read tool, or drop them from ADR-017? Needed before OM-08.
2. Before KG-03: is the `status` enum (PENDING, MATCHED, SETTLED, PARTIALLY_SETTLED, FAILED, CANCELLED) enough for the ledger's settlement view?
3. #11 merged first, so this targets `main`. Please merge it **before** cutting `contracts-v1.0.0`, so the tag includes the ADR-017 alignment. If you'd rather tag now, I'll bump VERSION to 1.1.0 here instead.
