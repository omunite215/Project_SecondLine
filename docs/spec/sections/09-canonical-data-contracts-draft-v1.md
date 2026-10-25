## 9. CANONICAL DATA CONTRACTS (DRAFT V1, NOT IMPLEMENTED)

Names here define conceptual contracts; fields may be refined in implementation with a versioned ADR. Contracts are examples that must not be mistaken for completed APIs.

```json
{
  "scenario_manifest": {
    "scenario_id": "SCN-00042",
    "schema_version": "1.0",
    "generator_version": "break-factory@1.0",
    "seed": 42,
    "split": "eval",
    "break_type": "B7_SETTLEMENT_SHORTFALL",
    "pressure_level": "L2",
    "injection_condition": "none",
    "snapshot_hash": "sha256:<hex>",
    "source_snapshot_refs": ["gleif@date/hash", "iso20022@version"],
    "truth_ref": "internal:oracle/SCN-00042",
    "initial_state_ref": "snapshot/SCN-00042"
  },
  "proposed_action": {
    "action_id": "ACT-123",
    "run_id": "RUN-123",
    "break_id": "BRK-1042",
    "tool_schema_version": "1.0",
    "type": "CLASSIFY_TIMING",
    "reason_code": "PARTIAL_SETTLEMENT",
    "parameters": {"as_of_date": "2026-10-15"},
    "evidence_refs": [
      {"record_id": "SETTLE-882", "version": 3},
      {"record_id": "CUST-441", "version": 1}
    ],
    "expected_state_version": 7,
    "idempotency_key": "UUID",
    "agent_explanation": "The agent's untrusted narrative."
  },
  "server_decision_receipt": {
    "receipt_version": "1.0",
    "action_digest": "sha256:<canonical-action-hex>",
    "decision": "ALLOW|DENY|REVIEW_REQUIRED|EXECUTED",
    "policy_bundle_hash": "sha256:<hex>",
    "evidence_validation": "VALID|INVALID|INSUFFICIENT",
    "approval_id": null,
    "ledger_transaction_id": null,
    "previous_receipt_hash": "sha256:<hex>",
    "receipt_hash": "sha256:<hex>",
    "signature_key_id": "demo-signing-key-v1",
    "signature": "<optional P1/P2 detached signature>",
    "issued_at": "2026-10-15T18:00:00Z"
  }
}
```

**Contract cautions:** JSON shows *three related example documents*, not a single endpoint payload. Real action authorization requires cryptographically secure, non-forgeable identity/capabilities; client-supplied booleans like `requires_approval` are never trusted. Idempotency keys must be bound to actor/operation/payload and durable uniqueness. Resource IDs must be canonical and tenant-scoped. Signature verification requires published keys, rotation/expiry and a canonicalization scheme; unsigned hashes alone prove little against a privileged history rewriter. Keep `truth_ref` strictly server-internal; **never** include it in agent-visible scenario manifests or traces during test runs.

**Minimum persistent tables (suggested):** `institutions`, `instruments`, `trades`, `bookings`, `settlement_events`, `custodian_records`, `reference_data_versions`, `journal_headers`, `journal_lines`, `breaks`, `evidence_records`, `agent_runs`, `tool_actions`, `policy_decisions`, `approval_requests`, `approval_decisions`, `outbox`, `audit_receipts`, `scenario_manifests`, `experiment_runs`, `grade_results`, `state_snapshots`. Use database migrations and scoped indexes/constraints. Oracle tables logically and access-wise isolated.

**Key DB constraints:** `UNIQUE (actor_scope, operation_type, idempotency_key)` and deterministic payload hash match; check constraints/transactions for balanced journal posting and positive/valid quantities (multirow balances enforced in service DB transaction, not a naive row check); optimistic `state_version` or row locks; immutable committed journal; uniqueness of outbox event ID; explicit account/currency identity; immutable approvals bound to action+state digest. DB isolation choice must be documented and tested for write races.

