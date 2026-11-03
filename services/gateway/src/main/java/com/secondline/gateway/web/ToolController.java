package com.secondline.gateway.web;

import com.fasterxml.jackson.databind.JsonNode;
import com.secondline.contracts.CanonicalJson;
import com.secondline.contracts.ContractException;
import com.secondline.contracts.generated.ErrorCode;
import com.secondline.gateway.GatewayException;
import com.secondline.gateway.pipeline.ToolCall;
import com.secondline.gateway.pipeline.ToolPipeline;
import com.secondline.gateway.pipeline.ToolResult;
import com.secondline.gateway.token.RunTokens;
import java.util.UUID;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

/**
 * POST /v1/runs/{runId}/tools/{tool} (gateway-tools.yaml). The controller only parses: a strict JSON body
 * (no duplicate keys, no floats: CanonicalJson), the run id, and the bearer token. Everything else is the
 * pipeline's (Om's) decision. A malformed run id gets the token's answer, so it isn't a probe.
 */
@RestController
public class ToolController {
    private static final java.util.regex.Pattern UUID_SHAPE =
            java.util.regex.Pattern.compile("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$");

    private final ToolPipeline pipeline;
    private final org.springframework.beans.factory.ObjectProvider<io.micrometer.tracing.Tracer> tracer;

    public ToolController(ToolPipeline pipeline, org.springframework.beans.factory.ObjectProvider<io.micrometer.tracing.Tracer> tracer) {
        this.pipeline = pipeline;
        this.tracer = tracer;
    }

    @PostMapping(path = "/v1/runs/{runId}/tools/{tool}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<JsonNode> call(@PathVariable String runId, @PathVariable String tool,
                                         @RequestHeader(name = "Authorization", required = false) String authorization,
                                         @RequestBody(required = false) String body) {
        UUID pathRunId;
        try {
            pathRunId = UUID.fromString(runId);
        } catch (IllegalArgumentException e) {
            throw RunTokens.denied();
        }
        JsonNode json;
        try {
            json = CanonicalJson.parse(body == null ? "" : body);
            CanonicalJson.canonicalize(json); // rejects float money, unsafe integers, lone surrogates (rule 3)
        } catch (ContractException e) {
            json = null;
        }
        if (json == null || !json.isObject()) { // every tool input is an object; "" parses to an empty node
            throw new GatewayException(ErrorCode.DOMAIN_INVALID, "request body must be one JSON object (no duplicate keys, no floats)");
        }
        tag(pathRunId, json);
        ToolResult r = pipeline.handle(new ToolCall(bearer(authorization), pathRunId, tool, json, UUID.randomUUID()));
        return ResponseEntity.status(r.status()).contentType(MediaType.APPLICATION_JSON).body(r.body());
    }

    /** Span tags (G13): run_id from the path, action_id only if it's a UUID. Never the token or any free text. */
    private void tag(UUID runId, JsonNode body) {
        io.micrometer.tracing.Tracer t = tracer.getIfAvailable();
        io.micrometer.tracing.Span span = t == null ? null : t.currentSpan();
        if (span == null) return;
        span.tag("run_id", runId.toString());
        JsonNode action = body.get("action_id");
        if (action != null && action.isTextual() && UUID_SHAPE.matcher(action.asText()).matches()) span.tag("action_id", action.asText());
    }

    /** The token after "Bearer ", or "" for anything else: another scheme's credential is never passed on. */
    static String bearer(String authorization) {
        if (authorization == null || !authorization.regionMatches(true, 0, "Bearer ", 0, 7)) return "";
        return authorization.substring(7).trim();
    }
}
