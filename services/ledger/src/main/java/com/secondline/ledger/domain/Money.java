package com.secondline.ledger.domain;

import com.secondline.ledger.LedgerException;
import java.math.BigDecimal;

/**
 * A positive posted amount in one currency. Scale must fit the currency's minor units (JPY 0, others 2);
 * more decimals are rejected, never rounded (ADR-016). Normalised, so 10.1 and 10.10 are equal.
 */
public record Money(BigDecimal amount, Currency currency) {
    public Money {
        if (currency == null) throw LedgerException.domainInvalid("money without currency");
        amount = Decimals.positive(amount, currency.minorUnits(), "amount in " + currency);
    }

    public static Money of(String decimal, Currency currency) {
        return new Money(Decimals.parse(decimal, "amount"), currency);
    }
}
