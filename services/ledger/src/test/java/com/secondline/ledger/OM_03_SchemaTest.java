package com.secondline.ledger;

import static com.secondline.ledger.LedgerDb.app;
import static com.secondline.ledger.LedgerDb.exec;
import static com.secondline.ledger.LedgerDb.query;
import static com.secondline.ledger.LedgerDb.superuser;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.sql.SQLException;
import java.util.UUID;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** OM-03 §5 §9 ADR-015 ADR-016: reference + operational tables, keyed (ns, id), checked in the DB. */
class OM_03_SchemaTest {
    static final String TRADE = "INSERT INTO ledger.trades (ns, id, instrument_id, counterparty_id, side, quantity,"
            + " price, currency, trade_date, settlement_date, record_version)"
            + " VALUES (?, ?, 'ins_A0000001', 'cpy_A0000001', 'BUY', ?::numeric, ?::numeric, 'USD', ?::date, ?::date, 1)";

    @BeforeAll
    static void schema() {
        LedgerDb.migrate();
    }

    /** One institution, counterparty and USD instrument in ns, the minimum a trade references. */
    static UUID seeded() throws SQLException {
        UUID ns = LedgerDb.newNamespace();
        exec(app(), "INSERT INTO ledger.institutions (ns, id, name) VALUES (?, 'ins_I0000001', 'Synthetic Broker')", ns);
        exec(app(), "INSERT INTO ledger.counterparties (ns, id, institution_id) VALUES (?, 'cpy_A0000001', 'ins_I0000001')", ns);
        exec(app(), "INSERT INTO ledger.instruments (ns, id, isin, currency) VALUES (?, 'ins_A0000001', 'US0000000001', 'USD')", ns);
        return ns;
    }

    static void sqlState(String state, ThrowingRunnable r) {
        assertThatThrownBy(r::run).isInstanceOf(SQLException.class).extracting("SQLState").isEqualTo(state);
    }

    interface ThrowingRunnable {
        void run() throws Exception;
    }

    @Test
    void OM_03_everyTableKeyedByNs() throws SQLException {
        String offenders = query(superuser(), """
                SELECT coalesce(string_agg(t.table_name, ','), '') FROM information_schema.tables t
                WHERE t.table_schema = 'ledger' AND t.table_type = 'BASE TABLE' AND t.table_name <> 'flyway_schema_history'
                  AND NOT EXISTS (
                    SELECT 1 FROM information_schema.table_constraints c
                    JOIN information_schema.key_column_usage k
                      ON k.constraint_name = c.constraint_name AND k.table_schema = c.table_schema
                    WHERE c.table_schema = 'ledger' AND c.table_name = t.table_name
                      AND c.constraint_type = 'PRIMARY KEY' AND k.ordinal_position = 1 AND k.column_name = 'ns')""");
        assertThat(offenders).isEmpty();
        // The card's reference + operational tables (the ledgers and positions come in V004).
        assertThat(query(superuser(), "SELECT string_agg(table_name, ',' ORDER BY table_name)"
                + " FROM information_schema.tables WHERE table_schema = 'ledger'").split(","))
                .contains("institutions", "counterparties", "instruments", "trades", "bookings", "allocations",
                        "settlement_instructions", "settlement_events", "custodian_records", "cash_accounts",
                        "reference_data_versions", "corporate_actions", "fx_snapshots", "evidence_records", "breaks");
    }

    @Test
    void OM_03_noCrossNamespaceFk() throws SQLException {
        seeded();
        UUID other = LedgerDb.newNamespace();
        sqlState("23503", () -> exec(app(), TRADE, other, "trd_B0000001", "100", "10.5", "2026-10-01", "2026-10-03"));
    }

    @Test
    void OM_03_quantityAndPriceChecks() throws SQLException {
        UUID ns = seeded();
        exec(app(), TRADE, ns, "trd_A0000001", "100", "10.50", "2026-10-01", "2026-10-03");
        sqlState("23514", () -> exec(app(), TRADE, ns, "trd_A0000002", "0", "10", "2026-10-01", "2026-10-03"));
        sqlState("23514", () -> exec(app(), TRADE, ns, "trd_A0000003", "10", "-1", "2026-10-01", "2026-10-03"));
        sqlState("23514", () -> exec(app(), TRADE, ns, "trd_A0000004", "10", "1", "2026-10-03", "2026-10-01"));
        sqlState("23514", () -> exec(app(), TRADE, ns, "trd_A0000005", "10.5", "1", "2026-10-01", "2026-10-03"));
    }

    @Test
    void OM_03_accountAndCurrencyChecks() throws SQLException {
        UUID ns = LedgerDb.newNamespace();
        for (String ccy : new String[] {"usd", "XXX"}) {
            sqlState("23514", () -> exec(app(),
                    "INSERT INTO ledger.instruments (ns, id, isin, currency) VALUES (?, 'ins_C0000001', 'US0000000002', ?)", ns, ccy));
        }
        sqlState("23514", () -> exec(app(), "INSERT INTO ledger.cash_accounts (ns, code, currency) VALUES (?, '9999', 'USD')", ns));
        sqlState("23514", () -> exec(app(), "INSERT INTO ledger.cash_accounts (ns, code, currency) VALUES (?, 'S100', 'USD')", ns));
        exec(app(), "INSERT INTO ledger.cash_accounts (ns, code, currency) VALUES (?, '1110', 'JPY')", ns);
        sqlState("23514", () -> exec(app(),
                "INSERT INTO ledger.instruments (ns, id, isin, currency) VALUES (?, 'ins_C0000002', 'not-an-isin', 'USD')", ns));
    }

    @Test
    void OM_03_evidenceKindsAreTheVisibleSet() throws SQLException {
        UUID ns = LedgerDb.newNamespace();
        exec(app(), "INSERT INTO ledger.evidence_records (ns, id, version, kind, fields, observed_at)"
                + " VALUES (?, 'ev_00000001', 1, 'CUSTODIAN_STATEMENT', '{}'::jsonb, now())", ns);
        sqlState("23514", () -> exec(app(), "INSERT INTO ledger.evidence_records (ns, id, version, kind, fields, observed_at)"
                + " VALUES (?, 'ev_00000002', 1, 'INTERNAL_BOOKING', '{}'::jsonb, now())", ns));
    }

    @Test
    void OM_03_noTruthColumns() throws SQLException {
        assertThat(query(superuser(), "SELECT coalesce(string_agg(table_name || '.' || column_name, ','), '')"
                + " FROM information_schema.columns WHERE table_schema = 'ledger'"
                + " AND column_name ~* '(root_cause|truth|canary|oracle|expected_state|allowed_outcome|forbidden_outcome)'"))
                .isEmpty();
    }

    @Test
    void OM_03_appCanOnlyUpdateBreakState() throws SQLException {
        UUID ns = seeded();
        exec(app(), TRADE, ns, "trd_A0000009", "100", "10.50", "2026-10-01", "2026-10-03");
        sqlState("42501", () -> exec(app(), "UPDATE ledger.trades SET price = 11 WHERE ns = ?", ns));
        sqlState("42501", () -> exec(app(), "DELETE FROM ledger.trades WHERE ns = ?", ns));
        exec(app(), "INSERT INTO ledger.breaks (ns, id, status) VALUES (?, 'brk_A0000001', 'OPEN')", ns);
        exec(app(), "UPDATE ledger.breaks SET state_version = state_version + 1, status = 'ESCALATED' WHERE ns = ?", ns);
        assertThat(query(app(), "SELECT state_version FROM ledger.breaks WHERE ns = ?", ns)).isEqualTo("1");
        sqlState("42501", () -> exec(app(), "UPDATE ledger.breaks SET id = 'brk_Z0000001' WHERE ns = ?", ns));
    }
}
