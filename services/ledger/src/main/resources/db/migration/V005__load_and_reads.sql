-- OM-04 §5 §9 §12 ADR-015 ADR-019: what the WorldBundle loader writes and the read tools need.
-- Runs on empty tables (no namespace is loaded before OM-04), so NOT NULL columns need no back-fill.

-- Namespaces: created EMPTY, loaded once (snapshot is write-once), retired, never deleted (ADR-019).
-- state_version is the ns-wide counter as-of reads use; it only moves forward.
ALTER TABLE ledger.namespaces
    ALTER COLUMN snapshot_id DROP NOT NULL,
    ADD COLUMN state_version bigint NOT NULL DEFAULT 0 CHECK (state_version >= 0),
    ADD COLUMN status text NOT NULL DEFAULT 'EMPTY' CHECK (status IN ('EMPTY', 'LOADED', 'RETIRED')),
    ADD COLUMN loaded_at timestamptz NULL,
    ADD CHECK (status = 'EMPTY' OR snapshot_id IS NOT NULL);
GRANT UPDATE (snapshot_id, status, loaded_at, state_version) ON ledger.namespaces TO ledger_app;

CREATE FUNCTION ledger.namespace_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.snapshot_id IS NOT NULL AND NEW.snapshot_id IS DISTINCT FROM OLD.snapshot_id THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'namespace snapshot is write-once (ADR-015)';
    END IF;
    IF NEW.state_version < OLD.state_version THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'namespace state_version only moves forward';
    END IF;
    IF OLD.status = 'RETIRED' AND NEW.status <> 'RETIRED' THEN
        RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'a retired namespace stays retired';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER namespaces_guard BEFORE UPDATE ON ledger.namespaces
    FOR EACH ROW EXECUTE FUNCTION ledger.namespace_guard();

-- Ledger entries: the ns version they were committed at (stamped by the DB, never by the app), the trade they
-- book, and an opaque ref the agent can cite (evidence_ref.record_id must be an opaque_id, not a uuid).
-- Default refs are hex, which can't spell dev/eval/blind/test.
ALTER TABLE ledger.journal_headers
    ADD COLUMN committed_version bigint NOT NULL DEFAULT 0,
    ADD COLUMN trade_id ledger.oid NULL,
    ADD COLUMN ref ledger.oid NOT NULL DEFAULT ('jnl_' || substr(md5(random()::text), 1, 16)),
    ADD UNIQUE (ns, ref),
    ADD FOREIGN KEY (ns, trade_id) REFERENCES ledger.trades (ns, id);
ALTER TABLE ledger.securities_entries
    ADD COLUMN committed_version bigint NOT NULL DEFAULT 0,
    ADD COLUMN trade_id ledger.oid NULL,
    ADD COLUMN ref ledger.oid NOT NULL DEFAULT ('mov_' || substr(md5(random()::text), 1, 16)),
    ADD UNIQUE (ns, ref),
    ADD FOREIGN KEY (ns, trade_id) REFERENCES ledger.trades (ns, id);

CREATE FUNCTION ledger.stamp_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    -- Unknown ns → 0, so the (ns) foreign key still rejects the row with its usual error (mapped to DOMAIN_INVALID).
    NEW.committed_version := coalesce((SELECT state_version FROM ledger.namespaces WHERE ns = NEW.ns), 0);
    RETURN NEW;
END $$;
CREATE TRIGGER journal_headers_stamp BEFORE INSERT ON ledger.journal_headers
    FOR EACH ROW EXECUTE FUNCTION ledger.stamp_version();
CREATE TRIGGER securities_entries_stamp BEFORE INSERT ON ledger.securities_entries
    FOR EACH ROW EXECUTE FUNCTION ledger.stamp_version();

-- Reference + operational records, as the WorldBundle 2.0 carries them.
ALTER TABLE ledger.instruments ADD COLUMN name text NULL CHECK (length(name) <= 80);
ALTER TABLE ledger.trades
    ADD COLUMN status text NOT NULL DEFAULT 'BOOKED' CHECK (status IN ('BOOKED', 'SETTLED', 'FAILED', 'CANCELLED'));
ALTER TABLE ledger.reference_data_versions
    ADD COLUMN ref text NOT NULL,
    ADD COLUMN retrieved_at timestamptz NOT NULL,
    ADD UNIQUE (ns, ref);

-- Evidence is shown to the agent verbatim and untrusted; its hash is computed here, never supplied.
ALTER TABLE ledger.evidence_records
    ADD COLUMN source_system text NOT NULL
        CHECK (source_system ~ '^[a-z0-9_-]{2,32}$' AND source_system !~* '(dev|eval|blind|test)'),
    ADD COLUMN text text NOT NULL CHECK (length(text) <= 4000),
    ADD COLUMN content_sha256 text NOT NULL DEFAULT '';
CREATE FUNCTION ledger.hash_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.content_sha256 := 'sha256:' || encode(sha256(convert_to(NEW.text, 'UTF8')), 'hex');
    RETURN NEW;
END $$;
CREATE TRIGGER evidence_records_hash BEFORE INSERT ON ledger.evidence_records
    FOR EACH ROW EXECUTE FUNCTION ledger.hash_evidence();

-- Breaks: the symptom reconciliation sees, never a break type (that is a root-cause label, ADR-015).
ALTER TABLE ledger.breaks
    DROP COLUMN break_type_visible,
    ADD COLUMN opened_at timestamptz NOT NULL,
    ADD COLUMN symptom text NOT NULL CHECK (symptom IN ('CASH_DIFFERENCE', 'POSITION_DIFFERENCE', 'UNMATCHED_TRADE',
        'SETTLEMENT_FAILURE', 'REFERENCE_MISMATCH')),
    ADD COLUMN currency ledger.ccy NULL,
    ADD COLUMN isin ledger.isin NULL,
    ADD COLUMN cash_difference numeric NULL CHECK (scale(cash_difference) <= 6),
    ADD COLUMN quantity_difference numeric NULL CHECK (scale(quantity_difference) = 0),
    ADD COLUMN record_version ledger.version NOT NULL DEFAULT 1;

CREATE TABLE ledger.break_trades (
    ns       uuid NOT NULL,
    break_id ledger.oid NOT NULL,
    trade_id ledger.oid NOT NULL,
    PRIMARY KEY (ns, break_id, trade_id),
    FOREIGN KEY (ns, break_id) REFERENCES ledger.breaks (ns, id),
    FOREIGN KEY (ns, trade_id) REFERENCES ledger.trades (ns, id)
);
-- Evidence is versioned (PK ns, id, version); a break names the record, the loader checks it exists.
CREATE TABLE ledger.break_evidence (
    ns        uuid NOT NULL,
    break_id  ledger.oid NOT NULL,
    record_id ledger.oid NOT NULL,
    PRIMARY KEY (ns, break_id, record_id),
    FOREIGN KEY (ns, break_id) REFERENCES ledger.breaks (ns, id)
);

-- Run registry (harness only). manifest_ref is stored, never dereferenced.
CREATE TABLE ledger.agent_runs (
    ns           uuid NOT NULL REFERENCES ledger.namespaces,
    run_id       uuid NOT NULL UNIQUE,
    controls     text NOT NULL CHECK (controls IN ('off', 'monitor', 'full')),
    agent_id     ledger.oid NOT NULL,
    manifest_ref text NOT NULL CHECK (manifest_ref ~ '^[A-Za-z0-9_][A-Za-z0-9_./-]{0,199}$' AND manifest_ref !~ '\.\.'),
    created_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (ns, run_id)
);
