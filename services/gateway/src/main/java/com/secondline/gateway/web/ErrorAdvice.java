package com.secondline.gateway.web;

import com.fasterxml.jackson.databind.JsonNode;
import com.secondline.contracts.Contracts;
import com.secondline.contracts.ErrorResponse;
import com.secondline.contracts.generated.ErrorCode;
import com.secondline.gateway.GatewayException;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.HttpMediaTypeException;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.servlet.NoHandlerFoundException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

/**
 * Every gateway error leaves as a contracts error_response with an errors.json code (golden rule 7), the same
 * pattern as the ledger's (OM-04). Messages are fixed text: no token, request value or stack trace reaches the
 * agent. An unknown route is a plain empty 404.
 */
@RestControllerAdvice
public class ErrorAdvice {
    private static final Logger LOG = LoggerFactory.getLogger(ErrorAdvice.class);

    @ExceptionHandler(GatewayException.class)
    public ResponseEntity<JsonNode> gateway(GatewayException e) {
        return respond(e.code(), e.detail(), UUID.randomUUID());
    }

    @ExceptionHandler(HttpMediaTypeException.class)
    public ResponseEntity<JsonNode> mediaType(Exception e) {
        return respond(ErrorCode.DOMAIN_INVALID, "request body must be application/json", UUID.randomUUID());
    }

    @ExceptionHandler(HttpRequestMethodNotSupportedException.class)
    public ResponseEntity<JsonNode> wrongMethod(Exception e) {
        return respond(ErrorCode.DOMAIN_INVALID, "method not supported on this route", UUID.randomUUID());
    }

    @ExceptionHandler({NoHandlerFoundException.class, NoResourceFoundException.class})
    public ResponseEntity<Void> noRoute(Exception e) {
        return ResponseEntity.notFound().build();
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<JsonNode> unexpected(Exception e) {
        UUID requestId = UUID.randomUUID();
        // Class name only: an exception message may carry a token or a request value.
        LOG.error("unexpected gateway error {}, request_id={}", e.getClass().getName(), requestId);
        return respond(ErrorCode.RETRYABLE_UNAVAILABLE, "unexpected gateway error; see request_id in the gateway log", requestId);
    }

    static ResponseEntity<JsonNode> respond(ErrorCode code, String message, UUID requestId) {
        return ResponseEntity.status(code.httpStatus().orElseThrow())
                .body(Contracts.MAPPER.valueToTree(new ErrorResponse(code, message, requestId.toString(), null)));
    }
}
