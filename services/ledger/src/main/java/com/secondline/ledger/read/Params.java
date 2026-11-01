package com.secondline.ledger.read;

import com.secondline.ledger.LedgerException;
import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.Set;
import java.util.regex.Pattern;

/** Read-tool input checks, mirroring common.schema.json; a bad value is DOMAIN_INVALID and never echoed. */
final class Params {
    private static final Pattern OPAQUE = Pattern.compile("^[a-z]{2,6}_[0-9A-Za-z]{8,32}$");
    private static final Pattern SPLIT = Pattern.compile("(?i)(dev|eval|blind|test)");
    private static final Pattern ISIN = Pattern.compile("^[A-Z]{2}[A-Z0-9]{9}[0-9]$");
    private static final Set<String> CURRENCIES = Set.of("USD", "EUR", "GBP", "CHF", "JPY");
    static final Set<String> BREAK_STATUSES = Set.of("OPEN", "CLASSIFIED", "PENDING_APPROVAL", "RESOLVED", "ESCALATED");

    private Params() {}

    static String id(String name, String v) {
        if (v == null || !OPAQUE.matcher(v).matches() || SPLIT.matcher(v).find()) throw bad(name);
        return v;
    }

    static String isin(String name, String v) {
        if (v == null || !ISIN.matcher(v).matches()) throw bad(name);
        return v;
    }

    static String currency(String name, String v) {
        if (v == null || !CURRENCIES.contains(v)) throw bad(name);
        return v;
    }

    static LocalDate date(String name, String v) {
        try {
            return LocalDate.parse(v);
        } catch (DateTimeParseException | NullPointerException e) {
            throw bad(name);
        }
    }

    static String breakStatus(String v) {
        if (!BREAK_STATUSES.contains(v)) throw bad("status");
        return v;
    }

    private static LedgerException bad(String name) {
        return LedgerException.domainInvalid("malformed parameter " + name);
    }
}
