package com.secondline.ledger;

import com.secondline.ledger.journal.CashPostingService;
import com.secondline.ledger.admin.AdminController;
import com.secondline.ledger.export.NamespaceExporter;
import com.secondline.ledger.load.BundleGuard;
import com.secondline.ledger.read.ReadController;
import com.secondline.ledger.read.ReadService;
import com.secondline.ledger.web.ErrorAdvice;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import com.secondline.ledger.load.WorldBundleLoader;
import com.secondline.ledger.ns.NamespaceRepository;
import com.secondline.ledger.journal.JournalRepository;
import com.secondline.ledger.journal.ReversalService;
import com.secondline.ledger.journal.SecuritiesPostingService;
import com.secondline.ledger.positions.PositionProjection;
import javax.sql.DataSource;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.jdbc.support.JdbcTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

/** Real services wired to the app role (ledger_svc), the way Spring wires them, without booting a context. */
public final class Services {
    public static final DataSource DS = LedgerDb.app();
    public static final JournalRepository REPO = new JournalRepository(JdbcClient.create(DS));
    // JdbcTransactionManager is what Spring Boot auto-configures.
    public static final TransactionTemplate TX = new TransactionTemplate(new JdbcTransactionManager(DS));

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

    public static NamespaceRepository namespaces() {
        return new NamespaceRepository(JdbcClient.create(DS));
    }

    private static final BundleGuard GUARD = new BundleGuard();  // loads the schemas once per JVM

    public static WorldBundleLoader loader() {
        return new WorldBundleLoader(JdbcClient.create(DS), GUARD, namespaces(), cash(), securities(), TX);
    }

    public static NamespaceExporter exporter() {
        return new NamespaceExporter(JdbcClient.create(DS), namespaces(), TX);
    }

    public static ReadService reads() {
        return new ReadService(JdbcClient.create(DS), namespaces(), TX);
    }

    /** The read routes with the real ErrorAdvice, without booting a context. */
    public static MockMvc readMvc() {
        return MockMvcBuilders.standaloneSetup(new ReadController(reads())).setControllerAdvice(new ErrorAdvice()).build();
    }

    /** The admin routes with the real ErrorAdvice, without booting a context. */
    public static MockMvc decisionsMvc() {
        return MockMvcBuilders.standaloneSetup(new com.secondline.ledger.decisions.DecisionController(namespaces(), JdbcClient.create(DS)))
                .setControllerAdvice(new ErrorAdvice()).build();
    }

    public static MockMvc adminMvc() {
        return MockMvcBuilders.standaloneSetup(new AdminController(namespaces(), loader(), exporter(), JdbcClient.create(DS)))
                .setControllerAdvice(new ErrorAdvice()).build();
    }
}
