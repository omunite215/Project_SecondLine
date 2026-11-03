package com.secondline.gateway.pipeline;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.UUID;

/** One agent tool call as the controller hands it over: raw bearer, the path's run id, the tool, the JSON body. */
public record ToolCall(String bearer, UUID pathRunId, String tool, JsonNode body, UUID requestId) {}
