package com.secondline.ledger.domain;

import com.secondline.ledger.LedgerException;
import java.math.BigDecimal;

/** Price per share in the trade currency, > 0, at most 8 decimals. */
public record Price(BigDecimal perShare, Currency currency) {
    public Price {
        if (currency == null) throw LedgerException.domainInvalid("price without currency");
        perShare = Decimals.positive(perShare, 8, "price");
    }

    public static Price of(String decimal, Currency currency) {
        return new Price(Decimals.parse(decimal, "price"), currency);
    }
}
