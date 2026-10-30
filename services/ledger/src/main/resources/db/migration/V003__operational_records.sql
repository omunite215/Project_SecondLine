-- OM-03 §5 §9: what the agent reads and cites. Record tables carry record_version (the version an
-- evidence_ref cites). No truth columns here, ever (REQ-006, rules/truth-isolation.md).

CREATE TABLE ledger.trades (
    ns              uuid NOT NULL REFERENCES ledger.namespaces,
    id              ledger.oid NOT NULL,
    instrument_id   ledger.oid NOT NULL,
    counterparty_id ledger.oid NOT NULL,
    side            text NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity        ledger.qty NOT NULL,
    price           ledger.price NOT NULL,
    currency        ledger.ccy NOT NULL,
    trade_date      date NOT NULL,
    settlement_date date NOT NULL CHECK (settlement_date >= trade_date),
    record_version  ledger.version NOT NULL,
    PRIMARY KEY (ns, id),
    FOREIGN KEY (ns, instrument_id) REFERENCES ledger.instruments (ns, id),
    FOREIGN KEY (ns, counterparty_id) REFERENCES ledger.counterparties (ns, id)
);

CREATE TABLE ledger.bookings (
    ns             uuid NOT NULL REFERENCES ledger.namespaces,
    id             ledger.oid NOT NULL,
    trade_id       ledger.oid NOT NULL,
    booked_at      timestamptz NOT NULL,
    record_version ledger.version NOT NULL,
    PRIMARY KEY (ns, id),
    FOREIGN KEY (ns, trade_id) REFERENCES ledger.trades (ns, id)
);

CREATE TABLE ledger.allocations (
    ns       uuid NOT NULL REFERENCES ledger.namespaces,
    id       ledger.oid NOT NULL,
    trade_id ledger.oid NOT NULL,
    quantity ledger.qty NOT NULL,
    PRIMARY KEY (ns, id),
    FOREIGN KEY (ns, trade_id) REFERENCES ledger.trades (ns, id)
);

CREATE TABLE ledger.settlement_events (
    ns               uuid NOT NULL REFERENCES ledger.namespaces,
    id               ledger.oid NOT NULL,
    trade_id         ledger.oid NOT NULL,
    status           text NOT NULL CHECK (status IN ('PENDING', 'MATCHED', 'SETTLED', 'PARTIALLY_SETTLED', 'FAILED', 'CANCELLED')),
    settled_quantity ledger.qty0 NOT NULL,
    event_time       timestamptz NOT NULL,
    record_version   ledger.version NOT NULL,
    PRIMARY KEY (ns, id),
    FOREIGN KEY (ns, trade_id) REFERENCES ledger.trades (ns, id)
);

CREATE TABLE ledger.custodian_records (
    ns             uuid NOT NULL REFERENCES ledger.namespaces,
    id             ledger.oid NOT NULL,
    isin           ledger.isin NOT NULL,
    quantity       ledger.qty0 NOT NULL,
    as_of          date NOT NULL,
    record_version ledger.version NOT NULL,
    PRIMARY KEY (ns, id)
);

CREATE TABLE ledger.corporate_actions (
    ns             uuid NOT NULL REFERENCES ledger.namespaces,
    id             ledger.oid NOT NULL,
    isin           ledger.isin NOT NULL,
    ca_type        text NOT NULL,
    ratio_num      integer NOT NULL CHECK (ratio_num > 0),
    ratio_den      integer NOT NULL CHECK (ratio_den > 0),
    ex_date        date NOT NULL,
    record_version ledger.version NOT NULL,
    PRIMARY KEY (ns, id)
);

-- World-bundle evidence (ADR-017): every kind except INTERNAL_BOOKING, which is the ledger's own rows.
CREATE TABLE ledger.evidence_records (
    ns          uuid NOT NULL REFERENCES ledger.namespaces,
    id          ledger.oid NOT NULL,
    version     ledger.version NOT NULL,
    kind        text NOT NULL CHECK (kind IN ('BROKER_CONFIRM', 'CUSTODIAN_STATEMENT', 'NOSTRO_STATEMENT',
                    'SETTLEMENT_STATUS', 'CA_NOTICE', 'SSI_RECORD', 'FX_RATE_NOTICE', 'COUNTERPARTY_MESSAGE')),
    fields      jsonb NOT NULL,
    observed_at timestamptz NOT NULL,
    PRIMARY KEY (ns, id, version)
);

-- Breaks show symptoms only; state_version is the optimistic-concurrency counter actions cite.
CREATE TABLE ledger.breaks (
    ns                 uuid NOT NULL REFERENCES ledger.namespaces,
    id                 ledger.oid NOT NULL,
    break_type_visible text NULL,
    status             text NOT NULL CHECK (status IN ('OPEN', 'IN_REVIEW', 'ESCALATED', 'RESOLVED')),
    state_version      bigint NOT NULL DEFAULT 0 CHECK (state_version >= 0),
    PRIMARY KEY (ns, id)
);
GRANT UPDATE (status, state_version) ON ledger.breaks TO ledger_app;
