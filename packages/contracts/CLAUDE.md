# packages/contracts — single source of truth for cross-service shapes (owners: both)
JSON Schema 2020-12 · OpenAPI 3.1 · errors.json · test vectors. Rules: .claude/rules/contracts.md.
```text
tools/<tool>.input.schema.json | .output.schema.json    one pair per §10 tool
actions/ receipts/ events/ scenario/ attacks/            ProposedAction, DecisionReceipt, envelope, manifest + world_bundle + truth, attack_pack
errors.json                                              typed codes (§8)
openapi/                                                 gateway-tools, ledger-internal, ledger-admin, review, eval
examples/                                                valid documents used by tests and mocks
test-vectors/                                            JCS + sha256 + Ed25519 vectors (SH-08)
py/                                                      generated pydantic package sl_contracts (never edit _generated/)
VERSION                                                  semver; bump on every change
```
Commands: `make contracts-check` · `make codegen`
Change flow: edit schema → bump VERSION → update examples/vectors → `make codegen` → `make contracts-check` → `/handoff` → both approve.
