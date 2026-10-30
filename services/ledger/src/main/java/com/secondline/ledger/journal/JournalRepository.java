package com.secondline.ledger.journal;

import com.secondline.ledger.domain.CashAccount;
import com.secondline.ledger.domain.Currency;
import com.secondline.ledger.domain.Money;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

/** SQL for both ledgers. Insert and select only: the app role has no UPDATE/DELETE on them (ADR-019). */
@Repository
public class JournalRepository {
    private final JdbcClient jdbc;

    public JournalRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    void insertCash(UUID entryId, CashEntry e, UUID reversesEntryId) {
        jdbc.sql("INSERT INTO ledger.journal_headers (ns, entry_id, entry_type, business_date, reverses_entry_id)"
                        + " VALUES (?, ?, ?, ?, ?)")
                .params(e.ns(), entryId, e.entryType(), e.businessDate(), reversesEntryId).update();
        int no = 1;
        for (CashLine l : e.lines()) {
            jdbc.sql("INSERT INTO ledger.journal_lines (ns, entry_id, line_no, account_code, currency, side, amount)"
                            + " VALUES (?, ?, ?, ?, ?, ?, ?)")
                    .params(e.ns(), entryId, no++, l.account().code(), l.money().currency().name(), l.side().name(),
                            l.money().amount())
                    .update();
        }
    }

    List<CashLine> cashLines(UUID ns, UUID entryId) {
        return jdbc.sql("SELECT account_code, side, currency, amount FROM ledger.journal_lines"
                        + " WHERE ns = ? AND entry_id = ? ORDER BY line_no")
                .params(ns, entryId)
                .query((rs, i) -> new CashLine(CashAccount.fromCode(rs.getString(1)), Side.valueOf(rs.getString(2)),
                        new Money(rs.getBigDecimal(4), Currency.of(rs.getString(3)))))
                .list();
    }

    /** Σ D − Σ C per currency for one account in a namespace. */
    Map<Currency, BigDecimal> cashBalance(UUID ns, CashAccount account) {
        Map<Currency, BigDecimal> out = new EnumMap<>(Currency.class);
        jdbc.sql("SELECT currency, sum(CASE side WHEN 'D' THEN amount ELSE -amount END) FROM ledger.journal_lines"
                        + " WHERE ns = ? AND account_code = ? GROUP BY currency")
                .params(ns, account.code())
                .query(rs -> {
                    out.put(Currency.of(rs.getString(1)), rs.getBigDecimal(2));
                });
        return out;
    }

    /** Entry header fields needed by reversals, or null when the entry doesn't exist in ns. */
    CashHeader cashHeader(UUID ns, UUID entryId) {
        return jdbc.sql("SELECT entry_type, business_date, reverses_entry_id FROM ledger.journal_headers"
                        + " WHERE ns = ? AND entry_id = ?")
                .params(ns, entryId)
                .query((rs, i) -> new CashHeader(rs.getString(1), rs.getObject(2, LocalDate.class),
                        rs.getObject(3, UUID.class)))
                .optional().orElse(null);
    }

    record CashHeader(String entryType, LocalDate businessDate, UUID reversesEntryId) {}
}
