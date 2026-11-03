package com.secondline.gateway.client;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.secondline.contracts.CanonicalJson;
import com.secondline.contracts.Contracts;
import java.net.http.HttpRequest;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * G9: POST {opa}/v1/data/secondline/decision with {input:{run, tool, action}}. A timeout (200 ms by default), an
 * error, an undefined result, an unknown decision or a missing bundle hash is RETRYABLE_UNAVAILABLE: OPA's silence
 * is never an ALLOW (§11 fail-safe).
 */
public class PolicyClient {
    private static final Set<String> DECISIONS = Set.of("ALLOW", "DENY", "REVIEW_REQUIRED");
    private static final Pattern SHA256 = Pattern.compile("^sha256:[0-9a-f]{64}$");

    private final String base;
    private final Duration timeout;

    public PolicyClient(String base, Duration timeout) {
        this.base = base.endsWith("/") ? base.substring(0, base.length() - 1) : base;
        this.timeout = timeout;
    }

    public PolicyDecision decide(JsonNode run, String tool, JsonNode action) {
        ObjectNode input = Contracts.MAPPER.createObjectNode();
        input.putObject("input").set("run", run);
        ((ObjectNode) input.get("input")).put("tool", tool).set("action", action);
        Http.Answer a = Http.send(HttpRequest.newBuilder(Http.uri(base, "/v1/data/secondline/decision"))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(CanonicalJson.canonicalize(input), StandardCharsets.UTF_8)),
                timeout, "policy");
        JsonNode r = a.body().path("result");
        String decision = r.path("decision").asText(null);
        String hash = r.path("bundle_hash").asText(null);
        if (a.status() != 200 || decision == null || !DECISIONS.contains(decision) || hash == null || !SHA256.matcher(hash).matches()) {
            throw Http.unavailable("policy", null);
        }
        return new PolicyDecision(decision, r.path("reason").asText(""), hash);
    }
}
