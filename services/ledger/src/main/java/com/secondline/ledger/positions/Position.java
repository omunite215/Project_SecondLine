package com.secondline.ledger.positions;

import java.math.BigDecimal;

/** trading = S100 + S200 (trade-date view); settled = S100 (what the custodian should show). */
public record Position(BigDecimal trading, BigDecimal settled) {
    public static final Position ZERO = new Position(BigDecimal.ZERO, BigDecimal.ZERO);

    public Position {
        trading = whole(trading);
        settled = whole(settled);
    }

    private static BigDecimal whole(BigDecimal v) {
        return v.setScale(0, java.math.RoundingMode.UNNECESSARY); // throws if a fraction ever appears
    }
}
