package com.secondline.ledger.domain;

import java.math.BigDecimal;

/** Whole shares, > 0 (fractional entitlements become cash in lieu, ADR-016). */
public record Quantity(BigDecimal units) {
    public Quantity {
        units = Decimals.positive(units, 0, "quantity");
    }

    public static Quantity of(String decimal) {
        return new Quantity(Decimals.parse(decimal, "quantity"));
    }
}
