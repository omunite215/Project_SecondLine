package com.secondline.ledger.journal;

import com.secondline.ledger.LedgerException;
import java.sql.SQLException;
import java.util.Set;
import java.util.function.Supplier;
import org.springframework.dao.DataAccessException;
import org.springframework.transaction.TransactionException;

/**
 * Maps DB-enforced rule violations to typed errors; anything else propagates unchanged. A violation found
 * by a deferred trigger surfaces at COMMIT as a TransactionException (TransactionSystemException), not a
 * DataAccessException, with either JdbcTransactionManager or DataSourceTransactionManager.
 */
final class Db {
    /** V004: P0002/P0003 unbalanced · P0004 lines added to an old entry · P0005 reversal of a reversal ·
     *  P0006 reversal isn't the mirror. Plus 23503 FK (unknown ns/entry) · 23505 unique · 23514 check. */
    private static final Set<String> DOMAIN = Set.of("P0002", "P0003", "P0004", "P0005", "P0006", "23503", "23505", "23514");

    private Db() {}

    static <T> T domain(Supplier<T> work) {
        try {
            return work.get();
        } catch (DataAccessException | TransactionException e) {
            String state = sqlState(e);
            if (state != null && DOMAIN.contains(state)) {
                throw new LedgerException("DOMAIN_INVALID", "rejected by the ledger DB (" + state + ")", e);
            }
            throw e;
        }
    }

    private static String sqlState(Throwable t) {
        for (Throwable c = t; c != null; c = c.getCause()) {
            if (c instanceof SQLException s && s.getSQLState() != null) return s.getSQLState();
        }
        return null;
    }
}
