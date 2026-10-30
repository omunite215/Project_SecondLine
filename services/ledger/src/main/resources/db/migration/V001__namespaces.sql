-- OM-03 ADR-015: one namespace per run; every ledger row carries ns and references this table.
CREATE TABLE ledger.namespaces (
    ns          uuid        PRIMARY KEY,
    snapshot_id text        NOT NULL CHECK (snapshot_id ~ '^sha256:[0-9a-f]{64}$'),
    created_at  timestamptz NOT NULL DEFAULT now()
);
