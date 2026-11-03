package com.secondline.gateway.pipeline;

import com.fasterxml.jackson.databind.JsonNode;

/** What the controller writes back: an HTTP status and a contract body (tool output or error_response). */
public record ToolResult(int status, JsonNode body) {}
