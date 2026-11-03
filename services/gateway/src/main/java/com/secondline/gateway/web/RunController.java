package com.secondline.gateway.web;

import com.fasterxml.jackson.databind.JsonNode;
import com.secondline.contracts.CanonicalJson;
import com.secondline.contracts.ContractException;
import com.secondline.contracts.generated.ErrorCode;
import com.secondline.gateway.GatewayException;
import com.secondline.gateway.runs.RunService;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

/** POST /v1/runs (harness only, gateway-tools.yaml): parse, then RunService decides. */
@RestController
public class RunController {
    private final RunService runs;

    public RunController(RunService runs) {
        this.runs = runs;
    }

    @PostMapping(path = "/v1/runs", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<JsonNode> create(@RequestHeader(name = "Authorization", required = false) String authorization,
                                           @RequestHeader(name = "Idempotency-Key", required = false) String idempotencyKey,
                                           @RequestBody(required = false) String body) {
        JsonNode json;
        try {
            json = CanonicalJson.parse(body == null ? "" : body);
            CanonicalJson.canonicalize(json);
        } catch (ContractException e) {
            json = null;
        }
        if (json == null || !json.isObject()) throw new GatewayException(ErrorCode.DOMAIN_INVALID, "request body must be one JSON object");
        RunService.Created c = runs.create(ToolController.bearer(authorization), idempotencyKey, json);
        return ResponseEntity.status(c.status()).contentType(MediaType.APPLICATION_JSON).body(c.body());
    }
}
