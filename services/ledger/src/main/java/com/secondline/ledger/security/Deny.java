package com.secondline.ledger.security;

import com.secondline.contracts.Contracts;
import com.secondline.contracts.ErrorResponse;
import com.secondline.contracts.generated.ErrorCode;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.UUID;

/**
 * Every realm refusal (no, bad, expired, wrong-realm or wrong-ns credential; a rejected request line) is the same
 * contract answer: 403 PERMISSION_DENIED, one fixed message. errors.json has no 401, and LedgerClient treats any
 * non-contract 4xx as unavailable; one answer also tells a caller nothing about why.
 */
final class Deny {
    static final String MESSAGE = "caller is not authorized for this route";

    private Deny() {}

    static void write(HttpServletResponse res) throws IOException {
        if (res.isCommitted()) return;
        res.resetBuffer();
        res.setStatus(ErrorCode.PERMISSION_DENIED.httpStatus().orElseThrow());
        res.setContentType("application/json");
        res.setHeader("Cache-Control", "no-store");
        res.getOutputStream().write(Contracts.MAPPER.writeValueAsBytes(
                new ErrorResponse(ErrorCode.PERMISSION_DENIED, MESSAGE, UUID.randomUUID().toString(), null)));
    }
}
