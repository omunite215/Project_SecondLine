package com.secondline.ledger;

import com.secondline.ledger.journal.CashPostingService;
import com.secondline.ledger.journal.JournalRepository;
import com.secondline.ledger.journal.ReversalService;
import com.secondline.ledger.journal.SecuritiesPostingService;
import com.secondline.ledger.positions.PositionProjection;
import javax.sql.DataSource;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

/** Real services wired to the app role (ledger_svc), the way Spring wires them, without booting a context. */
public final class Services {
    public static final DataSource DS = LedgerDb.app();
    public static final JournalRepository REPO = new JournalRepository(JdbcClient.create(DS));
    public static final TransactionTemplate TX = new TransactionTemplate(new DataSourceTransactionManager(DS));

    private Services() {}

    public static CashPostingService cash() {
        return new CashPostingService(REPO, TX);
    }

    public static PositionProjection positions() {
        return new PositionProjection(JdbcClient.create(DS));
    }

    public static SecuritiesPostingService securities() {
        return new SecuritiesPostingService(REPO, positions(), TX);
    }

    public static ReversalService reversals() {
        return new ReversalService(REPO, positions(), TX);
    }
}
