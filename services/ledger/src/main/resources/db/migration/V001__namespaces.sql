-- OM-03 ADR-015: one namespace per run; every ledger row carries ns and references this table.
CREATE TABLE ledger.namespaces (
    ns          uuid        PRIMARY KEY,
    snapshot_id text        NOT NULL CHECK (snapshot_id ~ '^sha256:[0-9a-f]{64}$'),
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- ADR-019: default privileges gave the app INSERT on every table, including Flyway's history. A forged
-- "applied" row would make Flyway skip a later migration, so the app may only read it.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ledger.flyway_schema_history FROM ledger_app;
