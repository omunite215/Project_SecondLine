package com.secondline.ledger.domain;

import com.secondline.ledger.LedgerException;

/** The synthetic bank's currency set (ADR-016 (a)) with ISO 4217 minor units. */
public enum Currency {
    USD(2), EUR(2), GBP(2), CHF(2), JPY(0);

    private final int minorUnits;

    Currency(int minorUnits) {
        this.minorUnits = minorUnits;
    }

    public int minorUnits() {
        return minorUnits;
    }

    public static Currency of(String code) {
        for (Currency c : values()) {
            if (c.name().equals(code)) return c;
        }
        throw LedgerException.domainInvalid("unsupported currency " + code);
    }
}
