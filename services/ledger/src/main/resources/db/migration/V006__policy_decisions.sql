-- OM-05 G8 §8 §12: every gateway decision (incl. each deny and the stage it came from), append-only.
-- Keyed (ns, decision_id); bound to a run registered in the same ns. `entry` keeps the exact JCS document so a
-- re-post can be compared byte-for-byte (identical → idempotent, different → IDEMPOTENCY_CONFLICT).
CREATE TABLE ledger.policy_decisions (
    ns                 uuid NOT NULL REFERENCES ledger.namespaces,
    decision_id        uuid NOT NULL,
    run_id             uuid NOT NULL,
    tool               text NOT NULL,
    action_id          uuid NULL,
    decision           text NOT NULL CHECK (decision IN ('ALLOW', 'DENY', 'REVIEW_REQUIRED')),
    error_code         text NULL,
    controls           text NOT NULL CHECK (controls IN ('off', 'monitor', 'full')),
    policy_bundle_hash text NULL CHECK (policy_bundle_hash ~ '^sha256:[0-9a-f]{64}$'),
    stage              text NOT NULL CHECK (stage IN ('token', 'binding', 'schema', 'guard', 'policy', 'ledger', 'routed')),
    at                 timestamptz NOT NULL,
    entry              text NOT NULL,
    recorded_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (ns, decision_id),
    FOREIGN KEY (ns, run_id) REFERENCES ledger.agent_runs (ns, run_id)
);

CREATE TRIGGER policy_decisions_immutable BEFORE UPDATE OR DELETE ON ledger.policy_decisions
    FOR EACH ROW EXECUTE FUNCTION ledger.forbid_change();
CREATE TRIGGER policy_decisions_no_truncate BEFORE TRUNCATE ON ledger.policy_decisions
    FOR EACH STATEMENT EXECUTE FUNCTION ledger.forbid_change();
