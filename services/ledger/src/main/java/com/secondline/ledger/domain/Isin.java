package com.secondline.ledger.domain;

import com.secondline.ledger.LedgerException;
import java.util.regex.Pattern;

/** ISIN shape (2 letters, 9 alphanumerics, check digit), as the ledger.isin domain enforces. */
public record Isin(String value) {
    private static final Pattern SHAPE = Pattern.compile("^[A-Z]{2}[A-Z0-9]{9}[0-9]$");

    public Isin {
        if (value == null || !SHAPE.matcher(value).matches()) throw LedgerException.domainInvalid("not an ISIN: " + value);
    }
}
