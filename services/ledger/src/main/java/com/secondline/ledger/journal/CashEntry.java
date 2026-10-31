package com.secondline.ledger.journal;

import com.secondline.ledger.LedgerException;
import com.secondline.ledger.domain.Currency;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * A cash journal entry, valid only if it has ≥ 2 lines and Σ D = Σ C in EVERY currency (I1). Checked here
 * before any SQL, and again by the DB at commit (V004).
 */
public record CashEntry(UUID ns, String entryType, LocalDate businessDate, List<CashLine> lines) {
    public CashEntry {
        if (ns == null || entryType == null || entryType.isBlank() || businessDate == null || lines == null) {
            throw LedgerException.domainInvalid("incomplete cash entry");
        }
        lines = List.copyOf(lines);
        if (lines.size() < 2) throw LedgerException.domainInvalid("a cash entry needs at least 2 lines");
        Map<Currency, BigDecimal> net = new EnumMap<>(Currency.class);
        for (CashLine l : lines) {
            BigDecimal signed = l.side() == Side.D ? l.money().amount() : l.money().amount().negate();
            net.merge(l.money().currency(), signed, BigDecimal::add);
        }
        net.forEach((ccy, n) -> {
            if (n.signum() != 0) throw LedgerException.domainInvalid("unbalanced in " + ccy + " by " + n.toPlainString());
        });
    }
}
