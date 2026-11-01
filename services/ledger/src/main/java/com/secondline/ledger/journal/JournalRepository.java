package com.secondline.ledger.journal;

import com.secondline.ledger.domain.CashAccount;
import com.secondline.ledger.domain.Currency;
import com.secondline.ledger.domain.Isin;
import com.secondline.ledger.domain.Money;
import com.secondline.ledger.domain.Quantity;
import com.secondline.ledger.domain.SecuritiesAccount;
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

    void insertCash(UUID entryId, CashEntry e, UUID reversesEntryId, String reason) {
        insertCash(entryId, e, reversesEntryId, reason, null);
    }

    void insertCash(UUID entryId, CashEntry e, UUID reversesEntryId, String reason, BookingRef ref) {
        header("journal_headers", e.ns(), entryId, e.entryType(), e.businessDate(), reversesEntryId, reason, ref);
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

    void insertSecurities(UUID entryId, SecuritiesEntry e, UUID reversesEntryId, String reason) {
        insertSecurities(entryId, e, reversesEntryId, reason, null);
    }

    void insertSecurities(UUID entryId, SecuritiesEntry e, UUID reversesEntryId, String reason, BookingRef ref) {
        header("securities_entries", e.ns(), entryId, e.entryType(), e.businessDate(), reversesEntryId, reason, ref);
        int no = 1;
        for (SecuritiesLine l : e.lines()) {
            jdbc.sql("INSERT INTO ledger.securities_lines (ns, entry_id, line_no, account_code, isin, side, quantity)"
                            + " VALUES (?, ?, ?, ?, ?, ?, ?)")
                    .params(e.ns(), entryId, no++, l.account().code(), l.isin().value(), l.side().name(), l.qty().units())
                    .update();
        }
    }

    List<SecuritiesLine> securitiesLines(UUID ns, UUID entryId) {
        return jdbc.sql("SELECT account_code, side, isin, quantity FROM ledger.securities_lines"
                        + " WHERE ns = ? AND entry_id = ? ORDER BY line_no")
                .params(ns, entryId)
                .query((rs, i) -> new SecuritiesLine(SecuritiesAccount.fromCode(rs.getString(1)),
                        Side.valueOf(rs.getString(2)), new Isin(rs.getString(3)), new Quantity(rs.getBigDecimal(4))))
                .list();
    }

    /** Header fields reversals need, or null when the entry doesn't exist in ns. */
    Header cashHeader(UUID ns, UUID entryId) {
        return header("ledger.journal_headers", ns, entryId);
    }

    Header securitiesHeader(UUID ns, UUID entryId) {
        return header("ledger.securities_entries", ns, entryId);
    }

    private Header header(String table, UUID ns, UUID entryId) {
        return jdbc.sql("SELECT business_date, reverses_entry_id, trade_id FROM " + table + " WHERE ns = ? AND entry_id = ?")
                .params(ns, entryId)
                .query((rs, i) -> new Header(rs.getObject(1, LocalDate.class), rs.getObject(2, UUID.class), rs.getString(3)))
                .optional().orElse(null);
    }

    record Header(LocalDate businessDate, UUID reversesEntryId, String tradeId) {}

    /** One header row; with a BookingRef its ref, trade_id and posted_at are explicit, otherwise DB defaults. */
    private void header(String table, UUID ns, UUID entryId, String type, java.time.LocalDate date, UUID reverses,
                        String reason, BookingRef ref) {
        if (ref == null) {
            jdbc.sql("INSERT INTO ledger." + table + " (ns, entry_id, entry_type, business_date, reverses_entry_id, reason)"
                            + " VALUES (?, ?, ?, ?, ?, ?)")
                    .params(ns, entryId, type, date, reverses, reason).update();
        } else {
            // A null ref falls back to the column's own default draw (V005), so callers may name only the trade.
            String draw = "'" + (table.equals("journal_headers") ? "jnl_" : "mov_") + "' || substr(md5(random()::text), 1, 16)";
            jdbc.sql("INSERT INTO ledger." + table + " (ns, entry_id, entry_type, business_date, reverses_entry_id, reason,"
                            + " ref, trade_id, posted_at) VALUES (?, ?, ?, ?, ?, ?, coalesce(?, " + draw + "), ?, coalesce(?, now()))")
                    .params(ns, entryId, type, date, reverses, reason, ref.ref(), ref.tradeId(), ref.postedAt()).update();
        }
    }
}
