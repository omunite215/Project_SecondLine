# packages/contracts — single source of truth for cross-service shapes (owners: both)
JSON Schema 2020-12 · OpenAPI 3.1 · errors.json · test vectors. Rules: .claude/rules/contracts.md.
```text
tools/<tool>.input.schema.json | .output.schema.json    one pair per §10 tool
actions/ receipts/ events/ scenario/ attacks/            ProposedAction, DecisionReceipt, envelope, manifest (agent) + run_manifest, world_bundle, ns_export, truth (x-privileged), attack_pack (x-privileged)
errors.json                                              typed codes (§8)
openapi/                                                 gateway-tools, ledger-internal, ledger-admin, review, eval
examples/                                                valid documents used by tests and mocks
test-vectors/                                            JCS + sha256 + Ed25519 vectors (SH-08)
py/                                                      generated pydantic package sl_contracts (never edit _generated/)
VERSION                                                  semver; bump on every change
```
Commands: `make contracts-check` · `make codegen`
Change flow: edit schema → bump VERSION → update examples/vectors → `make codegen` → `make contracts-check` → `/handoff` → both approve.
Evidence (ADR-017): `evidence_kind` is ADR-017's closed set; world bundles and `read_evidence` carry only `evidence_record_kind` (all but INTERNAL_BOOKING), with field keys allowlisted and typed per kind. An INTERNAL_BOOKING citation is an `evidence_ref` to a `trade_id` (read_trade `record_version`) or `entry_id` (read_bookings `record_version`); securities movements aren't agent-readable in v1, so they can't be cited.
IDs: `opaque_id`, `scenario_ref` and `source_system` reject dev/eval/blind/test in any case. Every generator (factory, ledger, gateway) re-draws on a hit, the same way in every split, so the id distribution can't reveal the split.
Digest (ADR-011, OM-02): `action_digest` = sha256 over JCS of `x-action-digest.include` in actions/proposed_action.schema.json (evidence_refs sorted). Java: libs/contracts-java ActionDigest; the audit-verifier reads the same annotation.
