# Handoff: Om → Kunal · contracts 2.1.0 for OM-05 (gateway)
Branch `om/OM-05-gateway` (stacked on `om/OM-04-ledger-reads`, i.e. on #37 2.0.0) · §8 §11 · ADR-013 ADR-014 · REQ-004 REQ-005

## What changed (additive on 2.0.0, so a minor bump)
- `runs/run_request.schema.json`: requires **`scenario_id`** (opaque_id; the run token carries it) and **`manifest_ref`** (passed on to the ledger run registry).
- `common.schema.json`:
  - `$defs/manifest_ref` is now the single definition (no `..`, no `truth/` or `generated/` path segment, no canary). `openapi/ledger-admin.yaml` uses it too.
  - `$defs/tool_name` = the tools in `tools/INDEX.json`.
- `runs/decision_log_entry.schema.json` + `POST /internal/v1/ns/{ns}/decisions` (ledger-internal): one entry per gateway tool call, denies included, with the `stage` that decided it.

## How to use it now
- Runner (KG-15), in order:
  1. `POST /admin/v1/ns`, then `:load` (ledger).
  2. `POST /v1/runs` (gateway) with the `Authorization: Bearer $GATEWAY_OPERATOR_TOKEN` header, an `Idempotency-Key` header, and a body like `{"ns", "controls", "agent_id", "scenario_id", "manifest_ref"}`. The response is a `run_token`.
  3. Hand the token to the agent / MCP adapter.
- Example: `packages/contracts/examples/runs/run_request.json`.
- `make bootstrap` now also writes `GATEWAY_OPERATOR_TOKEN` to `.env` and `secrets/gateway-signing.jwk` (needs a JDK on PATH). Re-run it once on your Mac.

## Breaking?
- For callers of `POST /v1/runs`, yes: two new required fields. No caller exists yet (the runner is todo), so there's nothing to migrate.

## What I need back
1. Approve on the OM-05 PR.
2. Is `manifest_ref` = the path under `experiments/manifests/` what the runner will have at run creation, or an id?
