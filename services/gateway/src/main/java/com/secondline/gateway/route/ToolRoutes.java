package com.secondline.gateway.route;

import com.fasterxml.jackson.databind.JsonNode;
import com.secondline.contracts.CanonicalJson;
import com.secondline.contracts.generated.ErrorCode;
import com.secondline.gateway.GatewayException;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * Tool → ledger routing (OM-05 Task 3). Risk comes from the contract's tools/INDEX.json; the read paths mirror
 * openapi/ledger-internal.yaml (a parity test fails if they drift). Every tool in INDEX.json has exactly one route.
 */
public final class ToolRoutes {
    private static final String BASE = "/internal/v1/ns/{ns}";
    private static final Map<String, ToolRoute> ROUTES = load();

    private ToolRoutes() {}

    /** The route for a tool, or PERMISSION_DENIED for anything that isn't a §10 tool. */
    public static ToolRoute of(String tool) {
        ToolRoute r = tool == null ? null : ROUTES.get(tool);
        if (r == null) throw new GatewayException(ErrorCode.PERMISSION_DENIED, "unknown tool");
        return r;
    }

    public static Collection<ToolRoute> all() {
        return ROUTES.values();
    }

    private static Map<String, ToolRoute> load() {
        JsonNode tools;
        try (InputStream in = ToolRoutes.class.getClassLoader().getResourceAsStream("contracts/tools/INDEX.json")) {
            if (in == null) throw new IllegalStateException("contracts/tools/INDEX.json missing from the classpath");
            tools = CanonicalJson.parse(new String(in.readAllBytes(), StandardCharsets.UTF_8)).path("tools");
        } catch (IOException e) {
            throw new IllegalStateException("cannot read tools/INDEX.json", e);
        }
        Map<String, ToolRoute> out = new TreeMap<>();
        tools.fieldNames().forEachRemaining(tool -> out.put(tool, route(tool, tools.path(tool).path("risk").asText())));
        return Map.copyOf(out);
    }

    private static ToolRoute route(String tool, String risk) {
        return switch (tool) {
            case "list_breaks" -> read(tool, "/breaks", "status");
            case "get_break" -> read(tool, "/breaks/{break_id}");
            case "read_trade" -> read(tool, "/trades/{trade_id}", "as_of_version");
            case "read_bookings" -> read(tool, "/trades/{trade_id}/bookings", "as_of_version");
            case "read_settlement_status" -> read(tool, "/trades/{trade_id}/settlement");
            case "read_positions" -> read(tool, "/positions", "isin", "as_of_version");
            case "read_custodian_statement" -> read(tool, "/custodian-statement", "as_of_date", "isin");
            case "read_corporate_actions" -> read(tool, "/corporate-actions", "isin");
            case "read_evidence" -> read(tool, "/evidence/{record_id}");
            case "read_reference_data" -> read(tool, "/reference-data/{record_id}");
            case "read_fx_snapshot" -> read(tool, "/fx", "base", "quote", "as_of_date");
            // No ledger read path in contracts yet: approvals land with OM-11, action status with OM-08/OM-14.
            case "get_action_status" -> unrouted(tool, risk, "ledger path pending OM-08/OM-14");
            case "get_approval_status" -> unrouted(tool, risk, "ledger path pending OM-11");
            // ADR-014: simulated messaging, budgeted by C_msg, no state change.
            case "request_counterparty_clarification" -> new ToolRoute(tool, risk, RouteKind.SIMULATED, null, List.of(), "ADR-014");
            default -> {
                if ("read".equals(risk)) throw new IllegalStateException("read tool without a route: " + tool);
                yield new ToolRoute(tool, risk, RouteKind.ACTION, BASE + "/actions", List.of(), null);
            }
        };
    }

    private static ToolRoute read(String tool, String path, String... query) {
        return new ToolRoute(tool, "read", RouteKind.READ, BASE + path, List.of(query), null);
    }

    private static ToolRoute unrouted(String tool, String risk, String note) {
        return new ToolRoute(tool, risk, RouteKind.UNROUTED, null, List.of(), note);
    }
}
