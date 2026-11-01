package com.secondline.ledger;

import static org.assertj.core.api.Assertions.assertThat;

import java.sql.Connection;
import java.sql.SQLException;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/**
 * OM-03 T-DOM-05 SEC-12 races: transaction B acts on rows transaction A has inserted but not committed.
 * B's BEFORE triggers can't see A's rows, so they don't fire. What closes the race is the foreign key: its
 * check doesn't see a parent row B's snapshot doesn't see, so B fails with 23503 (→ DOMAIN_INVALID) in READ
 * COMMITTED and REPEATABLE READ alike. These tests pin that outcome, whichever check gets there first.
 */
class OM_03_LedgerRaceTest {
    static final String HEADER = "INSERT INTO ledger.journal_headers (ns, entry_id, entry_type, business_date, reverses_entry_id, reason)"
            + " VALUES (?, ?, ?, '2026-10-01', ?, ?)";
    static final String LINE = "INSERT INTO ledger.journal_lines (ns, entry_id, line_no, account_code, currency, side, amount)"
            + " VALUES (?, ?, ?, ?, 'USD', ?, ?::numeric)";

    @BeforeAll
    static void schema() {
        LedgerDb.migrate();
    }

    static void run(Connection c, String sql, Object... args) throws SQLException {
        try (var st = c.prepareStatement(sql)) {
            for (int i = 0; i < args.length; i++) st.setObject(i + 1, args[i]);
            st.execute();
        }
    }

    static Connection open() throws SQLException {
        Connection c = LedgerDb.app().getConnection();
        c.setAutoCommit(false);
        return c;
    }

    /** Runs B on another thread; returns B's commit SQLState (null if it committed). */
    static CompletableFuture<String> inOtherTx(SqlWork work) {
        return CompletableFuture.supplyAsync(() -> {
            try (Connection b = open()) {
                try {
                    work.run(b);
                    b.commit();
                    return null;
                } catch (SQLException e) {
                    b.rollback();
                    return e.getSQLState();
                }
            } catch (SQLException e) {
                return "connect:" + e.getSQLState();
            }
        });
    }

    /** Every SQLState Db.domain maps to DOMAIN_INVALID that can stop B here. */
    static final java.util.Set<String> REJECTED = java.util.Set.of("23503", "P0004", "P0005", "P0006");

    interface SqlWork {
        void run(Connection c) throws SQLException;
    }

    @Test
    void T_DOM_05_lineRacingAnUncommittedHeaderIsRejected() throws Exception {
        UUID ns = LedgerDb.newNamespace();
        UUID e = UUID.randomUUID();
        try (Connection a = open()) {
            run(a, HEADER, ns, e, "BUY", null, null);
            run(a, LINE, ns, e, 1, "1300", "D", "100.00");
            run(a, LINE, ns, e, 2, "1210", "C", "100.00");
            CompletableFuture<String> b = inOtherTx(c -> {
                run(c, LINE, ns, e, 3, "1300", "D", "5.00");
                run(c, LINE, ns, e, 4, "1210", "C", "5.00");
            });
            Thread.sleep(500); // B is now blocked on the FK, waiting for A
            a.commit();
            assertThat(b.get(30, TimeUnit.SECONDS)).isIn(REJECTED);
        }
        assertThat(LedgerDb.query(LedgerDb.app(), "SELECT count(*) FROM ledger.journal_lines WHERE ns = ? AND entry_id = ?", ns, e))
                .isEqualTo("2");
    }

    /** B takes its REPEATABLE READ snapshot, then A commits; B's own reads can't see A's rows but its FK can. */
    static CompletableFuture<String> repeatableReadAfter(CompletableFuture<Void> snapshotTaken,
                                                         CompletableFuture<Void> aCommitted, SqlWork work) {
        return CompletableFuture.supplyAsync(() -> {
            try (Connection b = open()) {
                b.setTransactionIsolation(Connection.TRANSACTION_REPEATABLE_READ);
                try {
                    run(b, "SELECT 1"); // the snapshot is fixed here
                    snapshotTaken.complete(null);
                    aCommitted.get(30, TimeUnit.SECONDS);
                    work.run(b);
                    b.commit();
                    return null;
                } catch (SQLException e) {
                    b.rollback();
                    return e.getSQLState();
                }
            } catch (Exception e) {
                return "error:" + e;
            }
        });
    }

    @Test
    void T_DOM_05_repeatableReadCannotAddLinesToAnEntryCommittedAfterItsSnapshot() throws Exception {
        UUID ns = LedgerDb.newNamespace();
        UUID e = UUID.randomUUID();
        CompletableFuture<Void> snap = new CompletableFuture<>();
        CompletableFuture<Void> committed = new CompletableFuture<>();
        CompletableFuture<String> b = repeatableReadAfter(snap, committed, c -> {
            run(c, LINE, ns, e, 3, "1300", "D", "5.00");
            run(c, LINE, ns, e, 4, "1210", "C", "5.00");
        });
        snap.get(30, TimeUnit.SECONDS);
        LedgerDb.tx(LedgerDb.app(), LedgerDb.stmt(HEADER, ns, e, "BUY", null, null),
                LedgerDb.stmt(LINE, ns, e, 1, "1300", "D", "100.00"),
                LedgerDb.stmt(LINE, ns, e, 2, "1210", "C", "100.00"));
        committed.complete(null);
        assertThat(b.get(30, TimeUnit.SECONDS)).isIn(REJECTED);
        assertThat(LedgerDb.query(LedgerDb.app(), "SELECT count(*) FROM ledger.journal_lines WHERE ns = ? AND entry_id = ?", ns, e))
                .isEqualTo("2");
    }

    @Test
    void T_DOM_05_repeatableReadCannotReverseAReversalCommittedAfterItsSnapshot() throws Exception {
        UUID ns = LedgerDb.newNamespace();
        UUID orig = UUID.randomUUID();
        LedgerDb.tx(LedgerDb.app(), LedgerDb.stmt(HEADER, ns, orig, "BUY", null, null),
                LedgerDb.stmt(LINE, ns, orig, 1, "1300", "D", "100.00"),
                LedgerDb.stmt(LINE, ns, orig, 2, "1210", "C", "100.00"));
        UUID r1 = UUID.randomUUID();
        UUID r2 = UUID.randomUUID();
        CompletableFuture<Void> snap = new CompletableFuture<>();
        CompletableFuture<Void> committed = new CompletableFuture<>();
        CompletableFuture<String> b = repeatableReadAfter(snap, committed, c -> {
            run(c, HEADER, ns, r2, "REVERSAL", r1, "undo the undo");
            run(c, LINE, ns, r2, 1, "1300", "D", "100.00");
            run(c, LINE, ns, r2, 2, "1210", "C", "100.00");
        });
        snap.get(30, TimeUnit.SECONDS);
        LedgerDb.tx(LedgerDb.app(), LedgerDb.stmt(HEADER, ns, r1, "REVERSAL", orig, "first"),
                LedgerDb.stmt(LINE, ns, r1, 1, "1300", "C", "100.00"),
                LedgerDb.stmt(LINE, ns, r1, 2, "1210", "D", "100.00"));
        committed.complete(null);
        assertThat(b.get(30, TimeUnit.SECONDS)).isIn(REJECTED);
    }

    @Test
    void T_DOM_05_reversalRacingAnUncommittedReversalIsRejected() throws Exception {
        UUID ns = LedgerDb.newNamespace();
        UUID orig = UUID.randomUUID();
        LedgerDb.tx(LedgerDb.app(), LedgerDb.stmt(HEADER, ns, orig, "BUY", null, null),
                LedgerDb.stmt(LINE, ns, orig, 1, "1300", "D", "100.00"),
                LedgerDb.stmt(LINE, ns, orig, 2, "1210", "C", "100.00"));
        UUID r1 = UUID.randomUUID();
        UUID r2 = UUID.randomUUID();
        try (Connection a = open()) {
            run(a, HEADER, ns, r1, "REVERSAL", orig, "first");
            run(a, LINE, ns, r1, 1, "1300", "C", "100.00");
            run(a, LINE, ns, r1, 2, "1210", "D", "100.00");
            CompletableFuture<String> b = inOtherTx(c -> {
                run(c, HEADER, ns, r2, "REVERSAL", r1, "undo the undo");
                run(c, LINE, ns, r2, 1, "1300", "D", "100.00");
                run(c, LINE, ns, r2, 2, "1210", "C", "100.00");
            });
            Thread.sleep(500);
            a.commit();
            assertThat(b.get(30, TimeUnit.SECONDS)).isIn(REJECTED);
        }
    }
}
