package com.secondline.gateway.runs;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.secondline.contracts.Contracts;
import com.secondline.contracts.Digests;
import com.secondline.contracts.SchemaRegistry;
import com.secondline.contracts.generated.ErrorCode;
import com.secondline.gateway.GatewayException;
import com.secondline.gateway.client.LedgerClient;
import com.secondline.gateway.client.LedgerResponse;
import com.secondline.gateway.route.ToolRoute;
import com.secondline.gateway.route.ToolRoutes;
import com.secondline.gateway.token.RunGrant;
import com.secondline.gateway.token.RunTokens;
import com.secondline.gateway.token.SignedToken;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.temporal.ChronoUnit;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * POST /v1/runs (G5 G6). Operator-only: the bearer must equal GATEWAY_OPERATOR_TOKEN (constant-time), and an
 * unset secret denies every caller. The run is registered in the ledger first (the ledger owns run_id and checks
 * the ns is LOADED); only then is a token issued, with the controls from the ledger's answer and every §10 tool
 * (ADR-014: same surface in every condition). Idempotency-Key: same key + same body → the first answer; a
 * different body → IDEMPOTENCY_CONFLICT. The memory is bounded and lost on restart (documented OM-05 limit). Known
 * window: if the ledger registers the run but its answer times out, a retry registers a second run, because
 * ledger-admin register_run has no idempotency key yet (contract change, tracked for OM-07).
 */
public class RunService {
    public record Created(int status, JsonNode body) {}

    private record Remembered(String bodyDigest, Created answer) {}

    private static final List<String> ALL_TOOLS = ToolRoutes.all().stream().map(ToolRoute::tool).sorted().toList();

    private final byte[] operatorToken;
    private final LedgerClient ledger;
    private final RunTokens tokens;
    private final SchemaRegistry schemas;
    private final Map<String, Remembered> byKey;

    public RunService(String operatorToken, LedgerClient ledger, RunTokens tokens, SchemaRegistry schemas, int capacity) {
        this.operatorToken = operatorToken == null ? new byte[0] : operatorToken.getBytes(StandardCharsets.UTF_8);
        this.ledger = ledger;
        this.tokens = tokens;
        this.schemas = schemas;
        this.byKey = new LinkedHashMap<>(16, 0.75f, false) {
            @Override
            protected boolean removeEldestEntry(Map.Entry<String, Remembered> eldest) {
                return size() > capacity;
            }
        };
    }

    /** Serialised: two requests with one key can't both register a run. */
    public synchronized Created create(String operatorBearer, String idempotencyKey, JsonNode request) {
        if (!operator(operatorBearer)) throw new GatewayException(ErrorCode.PERMISSION_DENIED, "operator credential required");
        String key = uuid(idempotencyKey);
        if (!schemas.validate("runs/run_request.schema.json", request).isEmpty()) {
            throw new GatewayException(ErrorCode.DOMAIN_INVALID, "body does not match run_request");
        }
        String digest = Digests.sha256Canonical(request);
        Remembered seen = byKey.get(key);
        if (seen != null) {
            if (!seen.bodyDigest().equals(digest)) throw new GatewayException(ErrorCode.IDEMPOTENCY_CONFLICT, "Idempotency-Key reused with a different body");
            return seen.answer();
        }
        ObjectNode registration = Contracts.MAPPER.createObjectNode()
                .put("ns", request.get("ns").asText()).put("controls", request.get("controls").asText())
                .put("agent_id", request.get("agent_id").asText()).put("manifest_ref", request.get("manifest_ref").asText());
        LedgerResponse reg = ledger.registerRun(registration);
        if (reg.status() >= 300) return new Created(reg.status(), reg.body()); // e.g. 403 ns not LOADED; not remembered
        UUID runId = checkedRun(reg.body(), registration);
        SignedToken t = tokens.issue(new RunGrant(runId, UUID.fromString(registration.get("ns").asText()),
                request.get("scenario_id").asText(), request.get("agent_id").asText(), reg.body().get("controls").asText(), ALL_TOOLS));
        ObjectNode out = Contracts.MAPPER.createObjectNode().put("run_id", runId.toString()).put("token", t.token())
                .put("expires_at", t.expiresAt().truncatedTo(ChronoUnit.MILLIS).toString());
        Created created = new Created(201, out);
        byKey.put(key, new Remembered(digest, created));
        return created;
    }

    synchronized int rememberedKeys() {
        return byKey.size();
    }

    private boolean operator(String bearer) {
        if (operatorToken.length == 0 || bearer == null) return false;
        return MessageDigest.isEqual(operatorToken, bearer.getBytes(StandardCharsets.UTF_8));
    }

    /** The key in canonical lowercase form only, so "1-1-1-1-1" and its normalisation can't share a slot. */
    private static String uuid(String key) {
        try {
            String k = UUID.fromString(key == null ? "" : key).toString();
            if (!k.equals(key)) throw new IllegalArgumentException("not canonical");
            return k;
        } catch (IllegalArgumentException e) {
            throw new GatewayException(ErrorCode.DOMAIN_INVALID, "Idempotency-Key must be a canonical lowercase UUID");
        }
    }

    /** The ledger must have registered exactly the requested ns + controls; anything else issues no token. */
    private static UUID checkedRun(JsonNode answer, JsonNode asked) {
        try {
            UUID runId = UUID.fromString(answer.get("run_id").asText());
            if (!asked.get("ns").asText().equals(answer.get("ns").asText())
                    || !asked.get("controls").asText().equals(answer.get("controls").asText())) {
                throw new IllegalStateException("registration mismatch");
            }
            return runId;
        } catch (RuntimeException e) {
            throw new GatewayException(ErrorCode.RETRYABLE_UNAVAILABLE, "ledger run registration answer not usable", e);
        }
    }
}
