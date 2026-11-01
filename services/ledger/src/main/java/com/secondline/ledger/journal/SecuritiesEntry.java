package com.secondline.ledger.journal;

import com.secondline.ledger.LedgerException;
import com.secondline.ledger.domain.Isin;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/** A securities ledger entry: ≥ 2 lines and Σ D = Σ C per ISIN; the DB re-checks at commit (V004). */
public record SecuritiesEntry(UUID ns, String entryType, LocalDate businessDate, List<SecuritiesLine> lines) {
    public SecuritiesEntry {
        if (ns == null || entryType == null || entryType.isBlank() || businessDate == null || lines == null) {
            throw LedgerException.domainInvalid("incomplete securities entry");
        }
        lines = List.copyOf(lines);
        if (lines.size() < 2) throw LedgerException.domainInvalid("a securities entry needs at least 2 lines");
        Map<Isin, BigDecimal> net = new HashMap<>();
        for (SecuritiesLine l : lines) {
            BigDecimal signed = l.side() == Side.D ? l.qty().units() : l.qty().units().negate();
            net.merge(l.isin(), signed, BigDecimal::add);
        }
        net.forEach((isin, n) -> {
            if (n.signum() != 0) throw LedgerException.domainInvalid("unbalanced in " + isin.value() + " by " + n.toPlainString());
        });
    }
}
