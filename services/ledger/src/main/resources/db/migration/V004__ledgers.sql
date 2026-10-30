-- OM-03 §5 ADR-016: two double-entry ledgers and the position projection.
--   cash journal       money per currency (I1: Σ D = Σ C per currency, per entry)
--   securities ledger  quantity per ISIN  (Σ D = Σ C per ISIN, per entry); never cash
-- Balance is checked by DEFERRED constraint triggers at commit, so the DB rejects an unbalanced entry
-- even when the service is bypassed. Rows are append-only: the app has no UPDATE/DELETE grant (ADR-019)
-- and a trigger stops everyone else (T-DOM-05, SEC-12). Corrections are full reversals (reverses_entry_id).

CREATE TABLE ledger.journal_headers (
    ns                uuid NOT NULL REFERENCES ledger.namespaces,
    entry_id          uuid NOT NULL,
    entry_type        text NOT NULL,
    business_date     date NOT NULL,
    posted_at         timestamptz NOT NULL DEFAULT now(),
    reverses_entry_id uuid NULL CHECK (reverses_entry_id <> entry_id),
    PRIMARY KEY (ns, entry_id),
    UNIQUE (ns, reverses_entry_id),
    FOREIGN KEY (ns, reverses_entry_id) REFERENCES ledger.journal_headers (ns, entry_id)
);

CREATE TABLE ledger.journal_lines (
    ns           uuid NOT NULL,
    entry_id     uuid NOT NULL,
    line_no      integer NOT NULL CHECK (line_no >= 1),
    account_code char(4) NOT NULL CHECK (account_code IN ('1110', '1210', '1300', '1500', '1900', '2100', '4100', '4200', '4300')),
    currency     ledger.ccy NOT NULL,
    side         char(1) NOT NULL CHECK (side IN ('D', 'C')),
    amount       ledger.money NOT NULL,
    PRIMARY KEY (ns, entry_id, line_no),
    FOREIGN KEY (ns, entry_id) REFERENCES ledger.journal_headers (ns, entry_id)
);

CREATE TABLE ledger.securities_entries (
    ns                uuid NOT NULL REFERENCES ledger.namespaces,
    entry_id          uuid NOT NULL,
    entry_type        text NOT NULL,
    business_date     date NOT NULL,
    posted_at         timestamptz NOT NULL DEFAULT now(),
    reverses_entry_id uuid NULL CHECK (reverses_entry_id <> entry_id),
    PRIMARY KEY (ns, entry_id),
    UNIQUE (ns, reverses_entry_id),
    FOREIGN KEY (ns, reverses_entry_id) REFERENCES ledger.securities_entries (ns, entry_id)
);

CREATE TABLE ledger.securities_lines (
    ns           uuid NOT NULL,
    entry_id     uuid NOT NULL,
    line_no      integer NOT NULL CHECK (line_no >= 1),
    account_code char(4) NOT NULL CHECK (account_code IN ('S100', 'S200', 'S900')),
    isin         ledger.isin NOT NULL,
    side         char(1) NOT NULL CHECK (side IN ('D', 'C')),
    quantity     ledger.qty NOT NULL,
    PRIMARY KEY (ns, entry_id, line_no),
    FOREIGN KEY (ns, entry_id) REFERENCES ledger.securities_entries (ns, entry_id)
);

-- Projection, maintained in the posting transaction and recomputable from securities_lines (never cash).
CREATE TABLE ledger.positions (
    ns          uuid NOT NULL REFERENCES ledger.namespaces,
    isin        ledger.isin NOT NULL,
    trading_qty numeric NOT NULL CHECK (scale(trading_qty) = 0),
    settled_qty numeric NOT NULL CHECK (scale(settled_qty) = 0),
    PRIMARY KEY (ns, isin)
);
GRANT UPDATE (trading_qty, settled_qty) ON ledger.positions TO ledger_app;

-- ---- immutability -------------------------------------------------------------------------------
CREATE FUNCTION ledger.forbid_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION USING ERRCODE = 'P0001', MESSAGE = 'ledger rows are immutable (T-DOM-05): ' || TG_TABLE_NAME;
END $$;

CREATE TRIGGER journal_headers_immutable BEFORE UPDATE OR DELETE ON ledger.journal_headers
    FOR EACH ROW EXECUTE FUNCTION ledger.forbid_change();
CREATE TRIGGER journal_lines_immutable BEFORE UPDATE OR DELETE ON ledger.journal_lines
    FOR EACH ROW EXECUTE FUNCTION ledger.forbid_change();
CREATE TRIGGER securities_entries_immutable BEFORE UPDATE OR DELETE ON ledger.securities_entries
    FOR EACH ROW EXECUTE FUNCTION ledger.forbid_change();
CREATE TRIGGER securities_lines_immutable BEFORE UPDATE OR DELETE ON ledger.securities_lines
    FOR EACH ROW EXECUTE FUNCTION ledger.forbid_change();
CREATE TRIGGER journal_headers_no_truncate BEFORE TRUNCATE ON ledger.journal_headers
    FOR EACH STATEMENT EXECUTE FUNCTION ledger.forbid_change();
CREATE TRIGGER journal_lines_no_truncate BEFORE TRUNCATE ON ledger.journal_lines
    FOR EACH STATEMENT EXECUTE FUNCTION ledger.forbid_change();
CREATE TRIGGER securities_entries_no_truncate BEFORE TRUNCATE ON ledger.securities_entries
    FOR EACH STATEMENT EXECUTE FUNCTION ledger.forbid_change();
CREATE TRIGGER securities_lines_no_truncate BEFORE TRUNCATE ON ledger.securities_lines
    FOR EACH STATEMENT EXECUTE FUNCTION ledger.forbid_change();

-- ---- balance at commit ---------------------------------------------------------------------------
CREATE FUNCTION ledger.check_cash_entry() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    n int;
    bad text;
BEGIN
    SELECT count(*) INTO n FROM ledger.journal_lines WHERE ns = NEW.ns AND entry_id = NEW.entry_id;
    IF n < 2 THEN
        RAISE EXCEPTION USING ERRCODE = 'P0002', MESSAGE = 'cash entry needs at least 2 lines: ' || NEW.entry_id;
    END IF;
    SELECT string_agg(currency, ',') INTO bad FROM (
        SELECT currency FROM ledger.journal_lines WHERE ns = NEW.ns AND entry_id = NEW.entry_id
        GROUP BY currency
        HAVING sum(CASE side WHEN 'D' THEN amount ELSE -amount END) <> 0) unbalanced;
    IF bad IS NOT NULL THEN
        RAISE EXCEPTION USING ERRCODE = 'P0002', MESSAGE = 'unbalanced cash entry ' || NEW.entry_id || ' in ' || bad;
    END IF;
    RETURN NULL;
END $$;

CREATE FUNCTION ledger.check_securities_entry() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    n int;
    bad text;
BEGIN
    SELECT count(*) INTO n FROM ledger.securities_lines WHERE ns = NEW.ns AND entry_id = NEW.entry_id;
    IF n < 2 THEN
        RAISE EXCEPTION USING ERRCODE = 'P0003', MESSAGE = 'securities entry needs at least 2 lines: ' || NEW.entry_id;
    END IF;
    SELECT string_agg(isin, ',') INTO bad FROM (
        SELECT isin FROM ledger.securities_lines WHERE ns = NEW.ns AND entry_id = NEW.entry_id
        GROUP BY isin
        HAVING sum(CASE side WHEN 'D' THEN quantity ELSE -quantity END) <> 0) unbalanced;
    IF bad IS NOT NULL THEN
        RAISE EXCEPTION USING ERRCODE = 'P0003', MESSAGE = 'unbalanced securities entry ' || NEW.entry_id || ' in ' || bad;
    END IF;
    RETURN NULL;
END $$;

-- On the header too, so an entry with no lines at all is rejected; on lines, so lines added to an
-- old entry in a later transaction must still balance.
CREATE CONSTRAINT TRIGGER journal_headers_balanced AFTER INSERT ON ledger.journal_headers
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ledger.check_cash_entry();
CREATE CONSTRAINT TRIGGER journal_lines_balanced AFTER INSERT ON ledger.journal_lines
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ledger.check_cash_entry();
CREATE CONSTRAINT TRIGGER securities_entries_balanced AFTER INSERT ON ledger.securities_entries
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ledger.check_securities_entry();
CREATE CONSTRAINT TRIGGER securities_lines_balanced AFTER INSERT ON ledger.securities_lines
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ledger.check_securities_entry();
