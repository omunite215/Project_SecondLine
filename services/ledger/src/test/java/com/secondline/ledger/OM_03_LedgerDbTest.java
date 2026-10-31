package com.secondline.ledger;

import static com.secondline.ledger.LedgerDb.app;
import static com.secondline.ledger.LedgerDb.exec;
import static com.secondline.ledger.LedgerDb.migrator;
import static com.secondline.ledger.LedgerDb.query;
import static com.secondline.ledger.LedgerDb.stmt;
import static com.secondline.ledger.LedgerDb.tx;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.sql.SQLException;
import java.util.UUID;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** OM-03 §5 I1 T-DOM-01 T-DOM-05 SEC-12: the DB itself keeps both ledgers balanced and append-only. */
class OM_03_LedgerDbTest {
    static final String HEADER = "INSERT INTO ledger.journal_headers (ns, entry_id, entry_type, business_date) VALUES (?, ?, 'TEST', '2026-10-01')";
    static final String LINE = "INSERT INTO ledger.journal_lines (ns, entry_id, line_no, account_code, currency, side, amount) VALUES (?, ?, ?, ?, ?, ?, ?::numeric)";
    static final String SEC_HEADER = "INSERT INTO ledger.securities_entries (ns, entry_id, entry_type, business_date) VALUES (?, ?, 'TEST', '2026-10-01')";
    static final String SEC_LINE = "INSERT INTO ledger.securities_lines (ns, entry_id, line_no, account_code, isin, side, quantity) VALUES (?, ?, ?, ?, 'US0000000001', ?, ?::numeric)";

    @BeforeAll
    static void schema() {
        LedgerDb.migrate();
    }

    static void sqlState(String state, OM_03_SchemaTest.ThrowingRunnable r) {
        assertThatThrownBy(r::run).isInstanceOf(SQLException.class).extracting("SQLState").isEqualTo(state);
    }

    static UUID balancedUsd(UUID ns) throws SQLException {
        UUID e = UUID.randomUUID();
        tx(app(), stmt(HEADER, ns, e),
                stmt(LINE, ns, e, 1, "1300", "USD", "D", "1000.50"),
                stmt(LINE, ns, e, 2, "1210", "USD", "C", "1000.50"));
        return e;
    }

    @Test
    void T_DOM_01_dbRejectsUnbalancedEntryAtCommit() throws SQLException {
        UUID ns = LedgerDb.newNamespace();
        UUID e = UUID.randomUUID();
        sqlState("P0002", () -> tx(app(), stmt(HEADER, ns, e),
                stmt(LINE, ns, e, 1, "1300", "USD", "D", "10.00"),
                stmt(LINE, ns, e, 2, "1210", "USD", "C", "9.99")));
        assertThat(query(app(), "SELECT count(*) FROM ledger.journal_headers WHERE ns = ?", ns)).isEqualTo("0");
        balancedUsd(ns);
        assertThat(query(app(), "SELECT count(*) FROM ledger.journal_lines WHERE ns = ?", ns)).isEqualTo("2");
    }

    @Test
    void T_DOM_01_dbChecksEachCurrencySeparately() throws SQLException {
        UUID ns = LedgerDb.newNamespace();
        UUID bad = UUID.randomUUID();
        sqlState("P0002", () -> tx(app(), stmt(HEADER, ns, bad),
                stmt(LINE, ns, bad, 1, "1110", "USD", "D", "10"),
                stmt(LINE, ns, bad, 2, "1110", "EUR", "C", "10")));
        UUID fx = UUID.randomUUID(); // docs/domain.md FX conversion USD→EUR
        tx(app(), stmt(HEADER, ns, fx),
                stmt(LINE, ns, fx, 1, "1500", "USD", "D", "10.00"),
                stmt(LINE, ns, fx, 2, "1110", "USD", "C", "10.00"),
                stmt(LINE, ns, fx, 3, "1110", "EUR", "D", "9.21"),
                stmt(LINE, ns, fx, 4, "1500", "EUR", "C", "9.21"));
    }

    @Test
    void OM_03_entryWithoutLinesRejectedAtCommit() {
        UUID ns = LedgerDb.newNamespace();
        sqlState("P0002", () -> tx(app(), stmt(HEADER, ns, UUID.randomUUID())));
        sqlState("P0003", () -> tx(app(), stmt(SEC_HEADER, ns, UUID.randomUUID())));
    }

    @Test
    void OM_03_linesAddedLaterToAnOldEntryAreRejected() throws SQLException {
        // Stronger than "must still balance": a committed entry takes no more lines at all (P0004).
        UUID ns = LedgerDb.newNamespace();
        UUID e = balancedUsd(ns);
        sqlState("P0004", () -> tx(app(), stmt(LINE, ns, e, 3, "4100", "USD", "D", "0.01")));
    }

    @Test
    void T_DOM_05_committedEntryCannotGainLinesEvenBalanced() throws SQLException {
        UUID ns = LedgerDb.newNamespace();
        UUID e = balancedUsd(ns);
        sqlState("P0004", () -> tx(app(),
                stmt(LINE, ns, e, 3, "1300", "USD", "D", "500.00"),
                stmt(LINE, ns, e, 4, "1210", "USD", "C", "500.00")));
        assertThat(query(app(), "SELECT count(*) FROM ledger.journal_lines WHERE ns = ? AND entry_id = ?", ns, e)).isEqualTo("2");
    }

    static final String REVERSAL = "INSERT INTO ledger.journal_headers (ns, entry_id, entry_type, business_date, reverses_entry_id, reason)"
            + " VALUES (?, ?, 'REVERSAL', '2026-10-01', ?, 'raw')";

    @Test
    void OM_03_dbRejectsReversalOfAReversal() throws SQLException {
        UUID ns = LedgerDb.newNamespace();
        UUID a = balancedUsd(ns);
        UUID r1 = UUID.randomUUID();
        tx(app(), stmt(REVERSAL, ns, r1, a),
                stmt(LINE, ns, r1, 1, "1300", "USD", "C", "1000.50"),
                stmt(LINE, ns, r1, 2, "1210", "USD", "D", "1000.50"));
        UUID r2 = UUID.randomUUID();
        sqlState("P0005", () -> tx(app(), stmt(REVERSAL, ns, r2, r1),
                stmt(LINE, ns, r2, 1, "1300", "USD", "D", "1000.50"),
                stmt(LINE, ns, r2, 2, "1210", "USD", "C", "1000.50")));
    }

    @Test
    void OM_03_dbRejectsReversalThatIsNotTheMirror() throws SQLException {
        UUID ns = LedgerDb.newNamespace();
        UUID a = balancedUsd(ns);
        UUID squat = UUID.randomUUID(); // balanced, but not A's lines with sides swapped
        sqlState("P0006", () -> tx(app(), stmt(REVERSAL, ns, squat, a),
                stmt(LINE, ns, squat, 1, "1300", "USD", "C", "1.00"),
                stmt(LINE, ns, squat, 2, "1210", "USD", "D", "1.00")));
        UUID same = UUID.randomUUID(); // same sides as the original: not a reversal either
        sqlState("P0006", () -> tx(app(), stmt(REVERSAL, ns, same, a),
                stmt(LINE, ns, same, 1, "1300", "USD", "D", "1000.50"),
                stmt(LINE, ns, same, 2, "1210", "USD", "C", "1000.50")));
    }

    @Test
    void OM_03_reversalReferencingAnotherNamespaceFailsTheForeignKey() throws SQLException {
        UUID a = LedgerDb.newNamespace();
        UUID b = LedgerDb.newNamespace();
        UUID original = balancedUsd(a);
        UUID r = UUID.randomUUID();
        sqlState("23503", () -> tx(app(), stmt(REVERSAL, b, r, original),
                stmt(LINE, b, r, 1, "1300", "USD", "C", "1000.50"),
                stmt(LINE, b, r, 2, "1210", "USD", "D", "1000.50")));
    }

    @Test
    void OM_03_dbRejectsScaleAboveMinorUnits() {
        UUID ns = LedgerDb.newNamespace();
        for (String[] bad : new String[][] {{"USD", "1.234"}, {"JPY", "1.5"}, {"EUR", "0.001"}}) {
            UUID e = UUID.randomUUID();
            sqlState("23514", () -> tx(app(), stmt(HEADER, ns, e),
                    stmt(LINE, ns, e, 1, "1300", bad[0], "D", bad[1]),
                    stmt(LINE, ns, e, 2, "1210", bad[0], "C", bad[1])));
        }
    }

    @Test
    void T_DOM_05_committedRowsCannotBeUpdatedOrDeleted() throws SQLException {
        UUID ns = LedgerDb.newNamespace();
        UUID e = balancedUsd(ns);
        UUID s = UUID.randomUUID();
        tx(app(), stmt(SEC_HEADER, ns, s), stmt(SEC_LINE, ns, s, 1, "S200", "D", "5"), stmt(SEC_LINE, ns, s, 2, "S900", "C", "5"));
        sqlState("42501", () -> exec(app(), "UPDATE ledger.securities_lines SET quantity = 1 WHERE ns = ?", ns));
        sqlState("42501", () -> exec(app(), "UPDATE ledger.journal_lines SET amount = 1 WHERE ns = ?", ns));
        sqlState("42501", () -> exec(app(), "DELETE FROM ledger.journal_lines WHERE ns = ?", ns));
        sqlState("42501", () -> exec(app(), "DELETE FROM ledger.journal_headers WHERE ns = ?", ns));
        // Even the owner role is stopped by the trigger (defence in depth, ADR-019).
        sqlState("P0001", () -> exec(migrator(), "UPDATE ledger.journal_lines SET amount = 1 WHERE ns = ?", ns));
        sqlState("P0001", () -> exec(migrator(), "DELETE FROM ledger.journal_headers WHERE ns = ?", ns));
        sqlState("P0001", () -> exec(migrator(), "UPDATE ledger.securities_lines SET quantity = 1 WHERE ns = ?", ns));
        assertThat(query(app(), "SELECT sum(amount) FROM ledger.journal_lines WHERE ns = ? AND entry_id = ?", ns, e))
                .isEqualTo("2001.00");
    }

    @Test
    void OM_03_securitiesBalancePerIsin() throws SQLException {
        UUID ns = LedgerDb.newNamespace();
        UUID bad = UUID.randomUUID();
        sqlState("P0003", () -> tx(app(), stmt(SEC_HEADER, ns, bad),
                stmt(SEC_LINE, ns, bad, 1, "S200", "D", "100"),
                stmt(SEC_LINE, ns, bad, 2, "S900", "C", "99")));
        UUID ok = UUID.randomUUID();
        tx(app(), stmt(SEC_HEADER, ns, ok),
                stmt(SEC_LINE, ns, ok, 1, "S200", "D", "100"),
                stmt(SEC_LINE, ns, ok, 2, "S900", "C", "100"));
    }

    @Test
    void OM_03_cashLineRejectsSecuritiesAccount() {
        UUID ns = LedgerDb.newNamespace();
        UUID e = UUID.randomUUID();
        sqlState("23514", () -> tx(app(), stmt(HEADER, ns, e),
                stmt(LINE, ns, e, 1, "S100", "USD", "D", "1"),
                stmt(LINE, ns, e, 2, "1110", "USD", "C", "1")));
        UUID s = UUID.randomUUID();
        sqlState("23514", () -> tx(app(), stmt(SEC_HEADER, ns, s),
                stmt(SEC_LINE, ns, s, 1, "1110", "D", "1"),
                stmt(SEC_LINE, ns, s, 2, "S900", "C", "1")));
    }

    @Test
    void OM_03_zeroOrNegativeAmountsRejected() {
        UUID ns = LedgerDb.newNamespace();
        for (String amount : new String[] {"0", "-5.00", "1.0000001"}) {
            UUID e = UUID.randomUUID();
            sqlState("23514", () -> tx(app(), stmt(HEADER, ns, e),
                    stmt(LINE, ns, e, 1, "1300", "USD", "D", amount),
                    stmt(LINE, ns, e, 2, "1210", "USD", "C", amount)));
        }
    }

    @Test
    void OM_03_positionsWritableByAppOnly() throws SQLException {
        UUID ns = LedgerDb.newNamespace();
        exec(app(), "INSERT INTO ledger.positions (ns, isin, trading_qty, settled_qty) VALUES (?, 'US0000000001', 0, 0)", ns);
        exec(app(), "UPDATE ledger.positions SET trading_qty = 100 WHERE ns = ?", ns);
        sqlState("42501", () -> exec(app(), "DELETE FROM ledger.positions WHERE ns = ?", ns));
    }
}
