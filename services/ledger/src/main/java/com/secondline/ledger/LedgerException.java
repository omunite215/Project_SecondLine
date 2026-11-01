package com.secondline.ledger;

import com.secondline.contracts.generated.ErrorCode;

/** A typed ledger failure: no mutation happened (golden rule 7). Codes come only from errors.json (OM-02). */
public class LedgerException extends RuntimeException {
    private final ErrorCode code;
    private final String detail;

    public LedgerException(ErrorCode code, String message) {
        this(code, message, null);
    }

    public LedgerException(ErrorCode code, String message, Throwable cause) {
        super(code.name() + ": " + message, cause);
        if (code.graderOnly()) throw new IllegalArgumentException(code + " is grader-only; runtime services never raise it");
        this.code = code;
        this.detail = message;
    }

    public static LedgerException domainInvalid(String message) {
        return new LedgerException(ErrorCode.DOMAIN_INVALID, message);
    }

    public ErrorCode code() {
        return code;
    }

    /** The message without the code prefix: what an error_response carries. */
    public String detail() {
        return detail;
    }
}
