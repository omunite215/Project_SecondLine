package com.secondline.ledger.web;

import com.fasterxml.jackson.databind.JsonNode;
import com.secondline.contracts.Contracts;
import com.secondline.contracts.ErrorResponse;
import com.secondline.contracts.generated.ErrorCode;
import com.secondline.ledger.LedgerException;
import java.util.UUID;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

/**
 * Every ledger error leaves as a contracts error_response with an errors.json code (golden rule 7). Malformed
 * input is DOMAIN_INVALID and the message names the parameter, never its value.
 */
@RestControllerAdvice
public class ErrorAdvice {

    @ExceptionHandler(LedgerException.class)
    public ResponseEntity<JsonNode> ledger(LedgerException e) {
        return respond(e.code(), e.getMessage().substring(e.code().name().length() + 2));
    }

    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    public ResponseEntity<JsonNode> typeMismatch(MethodArgumentTypeMismatchException e) {
        return respond(ErrorCode.DOMAIN_INVALID, "malformed parameter " + e.getName());
    }

    @ExceptionHandler(MissingServletRequestParameterException.class)
    public ResponseEntity<JsonNode> missing(MissingServletRequestParameterException e) {
        return respond(ErrorCode.DOMAIN_INVALID, "missing parameter " + e.getParameterName());
    }

    private static ResponseEntity<JsonNode> respond(ErrorCode code, String message) {
        return ResponseEntity.status(code.httpStatus().orElseThrow())
                // Via the contracts mapper (NON_NULL): Spring's own would write "receipt_id": null, which the schema rejects.
                .body(Contracts.MAPPER.valueToTree(new ErrorResponse(code, message, UUID.randomUUID().toString(), null)));
    }
}
