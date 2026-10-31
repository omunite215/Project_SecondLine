package com.secondline.ledger.journal;

import com.secondline.ledger.LedgerException;
import com.secondline.ledger.domain.CashAccount;
import com.secondline.ledger.domain.Money;

/** One cash journal line: account + side + a positive amount in one currency. */
public record CashLine(CashAccount account, Side side, Money money) {
    public CashLine {
        if (account == null || side == null || money == null) throw LedgerException.domainInvalid("incomplete cash line");
    }

    public CashLine reversed() {
        return new CashLine(account, side.opposite(), money);
    }
}
