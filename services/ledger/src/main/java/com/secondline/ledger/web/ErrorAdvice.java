package com.secondline.ledger.web;

import com.fasterxml.jackson.databind.JsonNode;
import com.secondline.contracts.Contracts;
import com.secondline.contracts.ErrorResponse;
import com.secondline.contracts.generated.ErrorCode;
import com.secondline.ledger.LedgerException;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.HttpMediaTypeException;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.servlet.NoHandlerFoundException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

/**
 * Every ledger error leaves as a contracts error_response with an errors.json code (golden rule 7). Malformed
 * input is DOMAIN_INVALID and names the parameter or route, never a value. Anything unforeseen is logged here
 * and answered RETRYABLE_UNAVAILABLE with a fixed message: no stack trace or value reaches the caller.
 */
@RestControllerAdvice
public class ErrorAdvice {
    private static final Logger LOG = LoggerFactory.getLogger(ErrorAdvice.class);

    @ExceptionHandler(LedgerException.class)
    public ResponseEntity<JsonNode> ledger(LedgerException e) {
        return respond(e.code(), e.detail());
    }

    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    public ResponseEntity<JsonNode> typeMismatch(MethodArgumentTypeMismatchException e) {
        return respond(ErrorCode.DOMAIN_INVALID, "malformed parameter " + e.getName());
    }

    @ExceptionHandler(MissingServletRequestParameterException.class)
    public ResponseEntity<JsonNode> missing(MissingServletRequestParameterException e) {
        return respond(ErrorCode.DOMAIN_INVALID, "missing parameter " + e.getParameterName());
    }

    @ExceptionHandler({HttpMessageNotReadableException.class, HttpMediaTypeException.class})
    public ResponseEntity<JsonNode> unreadable(Exception e) {
        return respond(ErrorCode.DOMAIN_INVALID, "missing or unreadable request body");
    }

    @ExceptionHandler(HttpRequestMethodNotSupportedException.class)
    public ResponseEntity<JsonNode> wrongMethod(Exception e) {
        return respond(ErrorCode.DOMAIN_INVALID, "method not supported on this route");
    }

    /**
     * No route is plain HTTP 404 with no body, as OM-01 requires for hidden actuator endpoints: it's not a contract
     * response, and an empty 404 says nothing about what exists. Listed here so the catch-all doesn't make it a 503.
     */
    @ExceptionHandler({NoHandlerFoundException.class, NoResourceFoundException.class})
    public ResponseEntity<Void> noRoute(Exception e) {
        return ResponseEntity.notFound().build();
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<JsonNode> unexpected(Exception e) {
        String requestId = UUID.randomUUID().toString();
        LOG.error("unexpected ledger error, request_id={}", requestId, e);
        return respond(ErrorCode.RETRYABLE_UNAVAILABLE, "unexpected ledger error; see request_id in the ledger log", requestId);
    }

    private static ResponseEntity<JsonNode> respond(ErrorCode code, String message) {
        return respond(code, message, UUID.randomUUID().toString());
    }

    private static ResponseEntity<JsonNode> respond(ErrorCode code, String message, String requestId) {
        return ResponseEntity.status(code.httpStatus().orElseThrow())
                // Via the contracts mapper (NON_NULL): Spring's own would write "receipt_id": null, which the schema rejects.
                .body(Contracts.MAPPER.valueToTree(new ErrorResponse(code, message, requestId, null)));
    }
}
