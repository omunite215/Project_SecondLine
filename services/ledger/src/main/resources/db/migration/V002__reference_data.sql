-- OM-03 §5 §9 ADR-016 ADR-015: shared domains + reference data. Every table is keyed (ns, id).
-- Numbers are domains over unconstrained numeric with explicit scale/magnitude CHECKs: a NUMERIC(p,s)
-- column would silently ROUND extra decimals, and ADR-016 says a higher scale is rejected, never rounded.

CREATE DOMAIN ledger.ccy AS char(3) CHECK (VALUE IN ('USD', 'EUR', 'GBP', 'CHF', 'JPY'));
-- money: NUMERIC(24,6) capacity; the per-currency minor-unit rule (JPY 0, others 2) is checked on posting.
CREATE DOMAIN ledger.money   AS numeric CHECK (VALUE > 0 AND scale(VALUE) <= 6  AND VALUE < 1e18);
CREATE DOMAIN ledger.qty     AS numeric CHECK (VALUE > 0 AND scale(VALUE) = 0   AND VALUE < 1e20);
CREATE DOMAIN ledger.qty0    AS numeric CHECK (VALUE >= 0 AND scale(VALUE) = 0  AND VALUE < 1e20);
CREATE DOMAIN ledger.price   AS numeric CHECK (VALUE > 0 AND scale(VALUE) <= 8  AND VALUE < 1e16);
CREATE DOMAIN ledger.fx_rate AS numeric CHECK (VALUE > 0 AND scale(VALUE) <= 10 AND VALUE < 1e14);
-- Opaque ids (ADR-015, common.schema.json opaque_id): no meaning, never a split name.
CREATE DOMAIN ledger.oid AS text
    CHECK (VALUE ~ '^[a-z]{2,6}_[0-9A-Za-z]{8,32}$' AND VALUE !~* '(dev|eval|blind|test)');
CREATE DOMAIN ledger.isin AS char(12) CHECK (VALUE ~ '^[A-Z]{2}[A-Z0-9]{9}[0-9]$');
CREATE DOMAIN ledger.version AS integer CHECK (VALUE >= 1);

CREATE TABLE ledger.reference_data_versions (
    ns        uuid NOT NULL REFERENCES ledger.namespaces,
    id        ledger.oid NOT NULL,
    source    text NOT NULL,
    version   text NOT NULL,
    license   text NOT NULL,
    sha256    text NOT NULL CHECK (sha256 ~ '^sha256:[0-9a-f]{64}$'),
    PRIMARY KEY (ns, id)
);

CREATE TABLE ledger.institutions (
    ns   uuid NOT NULL REFERENCES ledger.namespaces,
    id   ledger.oid NOT NULL,
    name text NOT NULL,
    lei  char(20) NULL CHECK (lei ~ '^[A-Z0-9]{18}[0-9]{2}$'),
    PRIMARY KEY (ns, id)
);

CREATE TABLE ledger.counterparties (
    ns             uuid NOT NULL REFERENCES ledger.namespaces,
    id             ledger.oid NOT NULL,
    institution_id ledger.oid NOT NULL,
    PRIMARY KEY (ns, id),
    FOREIGN KEY (ns, institution_id) REFERENCES ledger.institutions (ns, id)
);

CREATE TABLE ledger.instruments (
    ns       uuid NOT NULL REFERENCES ledger.namespaces,
    id       ledger.oid NOT NULL,
    isin     ledger.isin NOT NULL,
    currency ledger.ccy NOT NULL,
    PRIMARY KEY (ns, id),
    UNIQUE (ns, isin)
);

-- SSI is reference data: read-only for the agent, never edited (B8).
CREATE TABLE ledger.settlement_instructions (
    ns              uuid NOT NULL REFERENCES ledger.namespaces,
    id              ledger.oid NOT NULL,
    counterparty_id ledger.oid NOT NULL,
    currency        ledger.ccy NOT NULL,
    record_version  ledger.version NOT NULL,
    PRIMARY KEY (ns, id),
    FOREIGN KEY (ns, counterparty_id) REFERENCES ledger.counterparties (ns, id)
);

-- Quote convention 1 BASE = rate QUOTE; only the designated source may revalue (B4).
CREATE TABLE ledger.fx_snapshots (
    ns          uuid NOT NULL REFERENCES ledger.namespaces,
    rate_id     ledger.oid NOT NULL,
    base        ledger.ccy NOT NULL,
    quote       ledger.ccy NOT NULL CHECK (quote <> base),
    rate        ledger.fx_rate NOT NULL,
    rate_source text NOT NULL,
    as_of       timestamptz NOT NULL,
    PRIMARY KEY (ns, rate_id)
);

-- The chart of accounts instantiated per namespace (docs/domain.md); securities accounts live per ISIN.
CREATE TABLE ledger.cash_accounts (
    ns       uuid NOT NULL REFERENCES ledger.namespaces,
    code     char(4) NOT NULL CHECK (code IN ('1110', '1210', '1300', '1500', '1900', '2100', '4100', '4200', '4300')),
    currency ledger.ccy NOT NULL,
    PRIMARY KEY (ns, code, currency)
);
