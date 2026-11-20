package com.secondline.ledger.journal;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.secondline.ledger.LedgerDb;
import com.secondline.ledger.LedgerException;
import java.util.UUID;
import javax.sql.DataSource;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.jdbc.support.JdbcTransactionManager;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * OM-03 golden rule 7: a rejection raised by the deferred trigger AT COMMIT is a typed DOMAIN_INVALID,
 * whichever transaction manager runs the commit (DataSourceTransactionManager wraps it differently).
 */
class OM_03_DbErrorMappingTest {
    @BeforeAll
    static void schema() {
        LedgerDb.migrate();
    }

    /** The JdbcClient and the transaction manager MUST share one DataSource instance, or each statement
     *  auto-commits on its own connection and the "commit-time" check fires per statement instead. */
    static void unbalancedAtCommit(java.util.function.Function<DataSource, PlatformTransactionManager> manager) {
        DataSource ds = LedgerDb.app();
        JdbcClient jdbc = JdbcClient.create(ds);
        PlatformTransactionManager tm = manager.apply(ds);
        UUID ns = LedgerDb.newNamespace();
        UUID e = UUID.randomUUID();
        assertThatThrownBy(() -> Db.domain(() -> new TransactionTemplate(tm).execute(s -> {
            jdbc.sql("INSERT INTO ledger.journal_headers (ns, entry_id, entry_type, business_date) VALUES (?, ?, 'RAW', '2026-10-01')")
                    .params(ns, e).update();
            jdbc.sql("INSERT INTO ledger.journal_lines (ns, entry_id, line_no, account_code, currency, side, amount)"
                    + " VALUES (?, ?, 1, '1300', 'USD', 'D', 10.00)").params(ns, e).update();
            jdbc.sql("INSERT INTO ledger.journal_lines (ns, entry_id, line_no, account_code, currency, side, amount)"
                    + " VALUES (?, ?, 2, '1210', 'USD', 'C', 9.99)").params(ns, e).update();
            return null;
        }))).isInstanceOf(LedgerException.class)
                .extracting(x -> ((LedgerException) x).code()).isEqualTo("DOMAIN_INVALID");
    }

    @Test
    void OM_03_commitTimeRejectionIsTyped_jdbcTransactionManager() {
        unbalancedAtCommit(JdbcTransactionManager::new);
    }

    @Test
    void OM_03_commitTimeRejectionIsTyped_dataSourceTransactionManager() {
        unbalancedAtCommit(DataSourceTransactionManager::new);
    }
}
