package com.secondline.ledger.domain;

import com.secondline.ledger.LedgerException;

/** Synthetic cash chart of accounts (docs/domain.md); every line pairs one with a currency. */
public enum CashAccount {
    NOSTRO("1110"),
    PENDING_SETTLEMENT("1210"),
    SECURITIES_AT_COST("1300"),
    FX_POSITION("1500"),
    /** The agent may never post here (B7); humans only. Enforced by OM-08. */
    SUSPENSE("1900"),
    FEES_PAYABLE("2100"),
    ROUNDING_PNL("4100"),
    FX_REVALUATION_PNL("4200"),
    REALISED_PNL("4300");

    private final String code;

    CashAccount(String code) {
        this.code = code;
    }

    public String code() {
        return code;
    }

    public static CashAccount fromCode(String code) {
        for (CashAccount a : values()) {
            if (a.code.equals(code)) return a;
        }
        throw LedgerException.domainInvalid("not a cash account: " + code);
    }
}
