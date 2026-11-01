package com.secondline.gateway;

import com.secondline.contracts.generated.ErrorCode;

/** A typed gateway refusal (golden rule 7): nothing was routed. Codes come only from errors.json (OM-02). */
public class GatewayException extends RuntimeException {
    private final ErrorCode code;
    private final String detail;

    public GatewayException(ErrorCode code, String detail) {
        this(code, detail, null);
    }

    public GatewayException(ErrorCode code, String detail, Throwable cause) {
        super(code.name() + ": " + detail, cause);
        if (code.graderOnly()) throw new IllegalArgumentException(code + " is grader-only; runtime services never raise it");
        this.code = code;
        this.detail = detail;
    }

    public ErrorCode code() {
        return code;
    }

    /** What an error_response carries: never a token, key or request value. */
    public String detail() {
        return detail;
    }
}
