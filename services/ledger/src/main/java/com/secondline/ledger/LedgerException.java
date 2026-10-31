package com.secondline.ledger;

/**
 * A typed ledger failure: no mutation happened (golden rule 7). The code is an errors.json code; it
 * becomes the contracts ErrorCode enum once OM-02 (#32) is on main.
 */
public class LedgerException extends RuntimeException {
    private final String code;

    public LedgerException(String code, String message) {
        super(code + ": " + message);
        this.code = code;
    }

    public LedgerException(String code, String message, Throwable cause) {
        super(code + ": " + message, cause);
        this.code = code;
    }

    public static LedgerException domainInvalid(String message) {
        return new LedgerException("DOMAIN_INVALID", message);
    }

    public String code() {
        return code;
    }
}
