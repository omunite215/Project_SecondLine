package com.secondline.gateway.client;

import com.fasterxml.jackson.databind.JsonNode;
import com.secondline.contracts.CanonicalJson;
import com.secondline.contracts.SchemaRegistry;
import com.secondline.contracts.generated.ErrorCode;
import com.secondline.gateway.GatewayException;
import com.secondline.gateway.route.RouteKind;
import com.secondline.gateway.route.ToolRoute;
import java.net.URLEncoder;
import java.net.http.HttpRequest;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * The gateway's only way to the ledger (ADR-013), always with a fresh service JWT (G12). G11: 5xx, timeouts,
 * refused connections, redirects and non-JSON answers are RETRYABLE_UNAVAILABLE; a 4xx passes through only if its body is a
 * contract error_response with a runtime code; any other 4xx is treated as unavailable, never as an outcome.
 */
public class LedgerClient {
    private static final Pattern PATH_VAR = Pattern.compile("\\{([a-z_]+)}");
    private static final SchemaRegistry SCHEMAS = SchemaRegistry.load();

    private final String base;
    private final ServiceTokens tokens;
    private final Duration timeout;

    public LedgerClient(String base, ServiceTokens tokens, Duration timeout) {
        this.base = base.endsWith("/") ? base.substring(0, base.length() - 1) : base;
        this.tokens = tokens;
        this.timeout = timeout;
    }

    /** A READ route: path variables and query values come from the (already schema-checked) tool input. */
    public LedgerResponse read(UUID ns, ToolRoute route, JsonNode input) {
        if (route.kind() == RouteKind.UNROUTED) throw Http.unavailable(route.tool(), null);
        if (route.kind() != RouteKind.READ) throw new IllegalArgumentException(route.tool() + " is not a read route");
        StringBuilder path = new StringBuilder();
        Matcher m = PATH_VAR.matcher(route.pathTemplate());
        while (m.find()) {
            String name = m.group(1);
            String value = name.equals("ns") ? ns.toString() : text(input, name);
            if (value == null) throw new GatewayException(ErrorCode.DOMAIN_INVALID, "missing " + name + " for " + route.tool());
            m.appendReplacement(path, Matcher.quoteReplacement(enc(value)));
        }
        m.appendTail(path);
        List<String> query = new ArrayList<>();
        for (String q : route.queryParams()) {
            String value = text(input, q);
            if (value != null) query.add(enc(q) + "=" + enc(value));
        }
        if (!query.isEmpty()) path.append('?').append(String.join("&", query));
        return call(HttpRequest.newBuilder(Http.uri(base, path.toString())).GET(), route.tool());
    }

    /** A write: the ProposedAction goes to the ledger byte-for-byte as JCS (the ledger re-validates it). */
    public LedgerResponse postAction(UUID ns, JsonNode action) {
        return call(json(Http.uri(base, "/internal/v1/ns/" + ns + "/actions"), action), "ledger");
    }

    /** ledger-admin register_run: {ns, controls, agent_id, manifest_ref} → {run_id, ns, controls}. */
    public LedgerResponse registerRun(JsonNode registration) {
        return call(json(Http.uri(base, "/admin/v1/runs"), registration), "ledger");
    }

    public LedgerResponse appendDecision(UUID ns, JsonNode entry) {
        return call(json(Http.uri(base, "/internal/v1/ns/" + ns + "/decisions"), entry), "decision log");
    }

    private HttpRequest.Builder json(java.net.URI uri, JsonNode body) {
        return HttpRequest.newBuilder(uri).header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(CanonicalJson.canonicalize(body), StandardCharsets.UTF_8));
    }

    private LedgerResponse call(HttpRequest.Builder req, String what) {
        Http.Answer a = Http.send(req.header("Authorization", "Bearer " + tokens.bearer())
                .header("Accept", "application/json"), timeout, what);
        if (a.status() >= 300 && a.status() < 400) throw Http.unavailable(what, null); // a redirect is never an outcome
        if (a.status() >= 400 && !SCHEMAS.validate("error_response.schema.json", a.body()).isEmpty()) {
            throw Http.unavailable(what, null); // not a contract error: a wrong path, a proxy page, a grader-only code
        }
        return new LedgerResponse(a.status(), a.body());
    }

    private static String text(JsonNode input, String field) {
        JsonNode v = input.get(field);
        return v == null || v.isNull() ? null : v.asText();
    }

    private static String enc(String v) {
        return URLEncoder.encode(v, StandardCharsets.UTF_8).replace("+", "%20");
    }
}
