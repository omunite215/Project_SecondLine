package com.secondline.ledger.domain;

import com.secondline.ledger.LedgerException;
import java.math.BigDecimal;
import java.util.regex.Pattern;

/** Decimal parsing and normal form shared by the value objects (docs/domain.md "JSON" precision row). */
final class Decimals {
    private static final Pattern UNSIGNED = Pattern.compile("^(0|[1-9][0-9]*)(\\.[0-9]+)?$");

    private Decimals() {}

    /** Parses a JSON decimal string with BigDecimal(String) only: no sign, exponent, spaces or float text. */
    static BigDecimal parse(String text, String what) {
        if (text == null || !UNSIGNED.matcher(text).matches()) {
            throw LedgerException.domainInvalid(what + " must be a decimal string, got " + text);
        }
        return new BigDecimal(text);
    }

    /** Smallest scale, never negative, so equal values are equal objects (100 stays 100, not 1E+2). */
    static BigDecimal normal(BigDecimal v) {
        BigDecimal s = v.stripTrailingZeros();
        return s.scale() < 0 ? s.setScale(0) : s;
    }

    /** Positive with at most maxScale decimals; a higher scale is rejected, never rounded (ADR-016). */
    static BigDecimal positive(BigDecimal v, int maxScale, String what) {
        if (v == null) throw LedgerException.domainInvalid(what + " is missing");
        BigDecimal n = normal(v);
        if (n.signum() <= 0) throw LedgerException.domainInvalid(what + " must be > 0, got " + v.toPlainString());
        if (n.scale() > maxScale) {
            throw LedgerException.domainInvalid(what + " has " + n.scale() + " decimals, at most " + maxScale + " allowed");
        }
        return n;
    }
}
