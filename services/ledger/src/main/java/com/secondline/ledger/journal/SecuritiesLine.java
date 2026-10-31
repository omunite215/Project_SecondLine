package com.secondline.ledger.journal;

import com.secondline.ledger.LedgerException;
import com.secondline.ledger.domain.Isin;
import com.secondline.ledger.domain.Quantity;
import com.secondline.ledger.domain.SecuritiesAccount;

/** One securities ledger line: account + side + whole shares of one ISIN. Never cash (ADR-016). */
public record SecuritiesLine(SecuritiesAccount account, Side side, Isin isin, Quantity qty) {
    public SecuritiesLine {
        if (account == null || side == null || isin == null || qty == null) {
            throw LedgerException.domainInvalid("incomplete securities line");
        }
    }

    public SecuritiesLine reversed() {
        return new SecuritiesLine(account, side.opposite(), isin, qty);
    }
}
