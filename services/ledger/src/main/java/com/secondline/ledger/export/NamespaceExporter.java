package com.secondline.ledger.export;

import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.secondline.contracts.Contracts;
import com.secondline.contracts.SchemaRegistry;
import com.secondline.ledger.domain.Currency;
import com.secondline.ledger.ns.NamespaceRepository;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.Comparator;
import java.util.List;
import java.util.UUID;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * Canonical namespace export (ADR-015, T-EVAL-03, contracts scenario/ns_export): signed balances per cash
 * account + currency (debit positive, at the currency's minor-unit scale) and per securities account + ISIN,
 * zero balances omitted, sorted by account string. Read in one REPEATABLE READ snapshot, and validated against
 * the contract before it is returned: an export that breaks the contract is a bug, never served.
 */
@Service
public class NamespaceExporter {
    static final String SCHEMA = "scenario/ns_export.schema.json";

    private final JdbcClient jdbc;
    private final NamespaceRepository namespaces;
    private final TransactionTemplate snapshot;
    private final SchemaRegistry schemas = SchemaRegistry.load();

    public NamespaceExporter(JdbcClient jdbc, NamespaceRepository namespaces, TransactionTemplate tx) {
        this.jdbc = jdbc;
        this.namespaces = namespaces;
        this.snapshot = new TransactionTemplate(tx.getTransactionManager());
        this.snapshot.setReadOnly(true);
        this.snapshot.setIsolationLevel(TransactionTemplate.ISOLATION_REPEATABLE_READ);
    }

    public ObjectNode export(UUID ns) {
        ObjectNode out = snapshot.execute(s -> build(ns));
        List<String> errors = schemas.validate(SCHEMA, out);
        if (!errors.isEmpty()) throw new IllegalStateException("ns export breaks " + SCHEMA + ": " + errors);
        return out;
    }

    private ObjectNode build(UUID ns) {
        NamespaceRepository.Row row = namespaces.requireLoaded(ns);
        ObjectNode out = Contracts.MAPPER.createObjectNode();
        out.put("export_version", "1.0");
        out.put("ns", ns.toString());
        out.put("snapshot_hash", row.snapshotId());
        out.put("state_version", row.stateVersion());

        record Cash(String account, String currency, String balance) {}
        List<Cash> cash = jdbc.sql("""
                        SELECT account_code, currency, sum(CASE side WHEN 'D' THEN amount ELSE -amount END)
                        FROM ledger.journal_lines WHERE ns = ? GROUP BY account_code, currency""")
                .param(ns)
                .query((rs, i) -> {
                    Currency ccy = Currency.of(rs.getString(2));
                    BigDecimal b = rs.getBigDecimal(3).setScale(ccy.minorUnits(), RoundingMode.UNNECESSARY);
                    return new Cash(rs.getString(1) + "-" + ccy.name(), ccy.name(), b.toPlainString());
                })
                .list().stream()
                .filter(c -> new BigDecimal(c.balance()).signum() != 0)
                .sorted(Comparator.comparing(Cash::account))
                .toList();
        ArrayNode cashOut = out.putArray("cash_balances");
        cash.forEach(c -> cashOut.addObject().put("account", c.account()).put("currency", c.currency()).put("balance", c.balance()));

        record Sec(String account, String isin, String quantity) {}
        List<Sec> sec = jdbc.sql("""
                        SELECT account_code, isin, sum(CASE side WHEN 'D' THEN quantity ELSE -quantity END)
                        FROM ledger.securities_lines WHERE ns = ? GROUP BY account_code, isin""")
                .param(ns)
                .query((rs, i) -> new Sec(rs.getString(1) + "-" + rs.getString(2), rs.getString(2),
                        rs.getBigDecimal(3).setScale(0, RoundingMode.UNNECESSARY).toPlainString()))
                .list().stream()
                .filter(q -> new BigDecimal(q.quantity()).signum() != 0)
                .sorted(Comparator.comparing(Sec::account))
                .toList();
        ArrayNode secOut = out.putArray("security_balances");
        sec.forEach(q -> secOut.addObject().put("account", q.account()).put("isin", q.isin()).put("quantity", q.quantity()));
        return out;
    }
}
