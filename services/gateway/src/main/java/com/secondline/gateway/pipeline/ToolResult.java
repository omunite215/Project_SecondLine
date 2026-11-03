package com.secondline.gateway.pipeline;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.UUID;

/**
 * What the controller writes back: an HTTP status and a contract body (tool output or error_response), plus the
 * run id the token proved (null when the token was refused), the only run id a span may be tagged with.
 */
public record ToolResult(int status, JsonNode body, UUID verifiedRunId) {
    public ToolResult(int status, JsonNode body) {
        this(status, body, null);
    }
}
