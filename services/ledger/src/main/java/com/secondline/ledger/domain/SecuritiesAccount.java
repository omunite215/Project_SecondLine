package com.secondline.ledger.domain;

import com.secondline.ledger.LedgerException;

/** Securities ledger accounts (docs/domain.md); every line pairs one with an ISIN. */
public enum SecuritiesAccount {
    CUSTODY("S100"),
    PENDING("S200"),
    STREET("S900");

    private final String code;

    SecuritiesAccount(String code) {
        this.code = code;
    }

    public String code() {
        return code;
    }

    public static SecuritiesAccount fromCode(String code) {
        for (SecuritiesAccount a : values()) {
            if (a.code.equals(code)) return a;
        }
        throw LedgerException.domainInvalid("not a securities account: " + code);
    }
}
