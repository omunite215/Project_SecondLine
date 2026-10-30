# Handoff: Om → Kunal · action_digest field set (2026-10-30)
Task: OM-02 · ADR-011 · §9 · REQ-005 · T-SEC-04 · contracts VERSION 1.0.0 → 1.1.0 (additive; `contracts-v1.0.0` is tagged on 3e11880)

## What changed
- `actions/proposed_action.schema.json` gains `x-action-digest`, which is the machine-readable definition of `action_digest`:
  `sha256:` + hex(SHA-256(JCS(RFC 8785) of exactly `run_id, break_id, tool_schema_version, type, reason_code, parameters, evidence_refs, expected_state_version`))`, with `evidence_refs` sorted by `(record_id, version)`.
- Excluded fields:
  - `action_id` and `request_id`: per request, so a retry digests the same.
  - `idempotency_key`: it indexes the digest rather than being part of it.
  - `agent_explanation`: C6, untrusted.
  - The actor isn't in the payload. Idempotency binds it through `UNIQUE(actor_scope, operation_type, key)`.
- JCS is restricted to integers. A non-integer number, or an integer outside ±(2^53−1), is an error, never ES6 float formatting. Golden rule 3 keeps money as strings, so a float in a digested document is already a bug.
- `scripts/contracts_check.py` checks that every `include` entry is a **required** property, listed once, and that `sort` keys are included. `make contracts-check` is OK.
- Java implementation: `libs/contracts-java` `ActionDigest`. `OM_02_digest_fields_match_schema_annotation` fails if Java drifts from the annotation.

- Golden vectors live in `packages/contracts/test-vectors/action_digest.json`: 3 cases, each with the action, the canonical string and the expected `sha256:`.
  - The expected values come from an independent stdlib Python JCS. `tests/kit/test_om_02_contracts.py` recomputes them on every kit run.
  - Java reproduces them byte for byte (`OM_02_digest_matches_golden_vector`).
  - SH-08 adds the full JCS/receipt suite next to this file.

## How to use it now
- The audit-verifier (KG-12) should read `x-action-digest` from the schema rather than hard-coding the list, and pass the vectors file.
- Fail-closed rules the Python side must match. Each of these is an error, never a digest:
  - a lone surrogate in any string (Java would otherwise encode it as `?`);
  - any non-integer number, including `7.0`;
  - an integer outside ±(2^53−1);
  - duplicate keys;
  - an evidence_ref that isn't exactly `{record_id: str, version: int}`.
- Keys and `record_id` sort by UTF-16 code units. Python's `sorted(k, key=lambda s: s.encode("utf-16-be"))` matches. `opaque_id` is ASCII, so plain `sorted` agrees today.
- The digest binds the action, not who acts on it. Approvals (OM-11) must store `approver` and `actor_scope` next to the digest, and idempotency (OM-09) binds `actor_scope` in its unique key.

## Breaking?
No. The annotation is additive, and nothing computed a digest before this.

## What I need back
1. Do you agree with the field set, especially leaving out `idempotency_key` and including `run_id`? An approval on the OM-02 PR counts as agreement.
2. Is restricting JCS to integers fine for the Python verifier? Python's `json` parses `1.0` as a float, so reject it the same way.
