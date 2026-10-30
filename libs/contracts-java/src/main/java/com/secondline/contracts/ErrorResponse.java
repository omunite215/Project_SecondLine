package com.secondline.contracts;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.secondline.contracts.generated.ErrorCode;

/** error_response.schema.json. Build only from {@link ErrorCode#runtimeValues()}; never ORACLE_MISMATCH. */
public record ErrorResponse(
        @JsonProperty("error_code") ErrorCode errorCode,
        @JsonProperty("message") String message,
        @JsonProperty("request_id") String requestId,
        @JsonProperty("receipt_id") String receiptId) {

    public ErrorResponse {
        if (errorCode == null || errorCode.graderOnly()) {
            throw new ContractException("error_response: runtime services can't return " + errorCode);
        }
        if (message == null || requestId == null) {
            throw new ContractException("error_response: message and request_id are required");
        }
    }
}
