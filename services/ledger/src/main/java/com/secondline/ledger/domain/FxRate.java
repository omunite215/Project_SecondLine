package com.secondline.ledger.domain;

import com.secondline.ledger.LedgerException;
import java.math.BigDecimal;
import java.time.Instant;

/** 1 BASE = rate QUOTE, from a named source at an instant (B4: only the designated rate may revalue). */
public record FxRate(String rateId, Currency base, Currency quote, BigDecimal rate, String rateSource, Instant asOf) {
    public FxRate {
        if (rateId == null || rateId.isBlank()) throw LedgerException.domainInvalid("fx rate without rate_id");
        if (rateSource == null || rateSource.isBlank()) throw LedgerException.domainInvalid("fx rate without rate_source");
        if (asOf == null) throw LedgerException.domainInvalid("fx rate without as_of");
        if (base == null || quote == null || base == quote) throw LedgerException.domainInvalid("fx rate needs two different currencies");
        rate = Decimals.positive(rate, 10, "fx rate");
    }
}
