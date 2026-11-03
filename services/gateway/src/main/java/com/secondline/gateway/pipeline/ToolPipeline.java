package com.secondline.gateway.pipeline;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.secondline.contracts.Contracts;
import com.secondline.contracts.ErrorResponse;
import com.secondline.contracts.generated.ErrorCode;
import com.secondline.gateway.GatewayException;
import com.secondline.gateway.client.DecisionLog;
import com.secondline.gateway.client.DecisionLogEntry;
import com.secondline.gateway.client.LedgerResponse;
import com.secondline.gateway.client.PolicyDecision;
import com.secondline.gateway.route.RouteKind;
import com.secondline.gateway.route.ToolRoute;
import com.secondline.gateway.route.ToolRoutes;
import com.secondline.gateway.token.RunClaims;
import com.secondline.gateway.client.LedgerClient;
import com.secondline.gateway.client.PolicyClient;
import com.secondline.gateway.guard.RunGuard;
import com.secondline.gateway.schema.InputSchemas;
import com.secondline.gateway.token.RunTokens;
import java.time.Clock;
import java.util.UUID;

/**
 * The gateway's policy enforcement point (OM-05 Task 4, §8 §11, ADR-013, ADR-014).
 *
 * <p>{@link #handle} (learn card; written by Claude at Om's request, 2026-11-03). The spec is
 * {@code OM_05_PipelineTest}. The building blocks (all tested in Task 3):
 * <ul>
 *   <li>{@link RunTokens#verify} → RunClaims, or PERMISSION_DENIED (token stage; no trusted ns, so not logged).</li>
 *   <li>binding: the body's run_id must equal the token's run_id (PERMISSION_DENIED).</li>
 *   <li>{@link InputSchemas#validate} (DOMAIN_INVALID) · {@link RunGuard#admit} (RUN_HALTED).</li>
 *   <li>{@link PolicyClient#decide}: only when controls=full and the tool's risk isn't read (ADR-014, G9).</li>
 *   <li>{@link com.secondline.gateway.route.ToolRoutes}: READ → {@link LedgerClient#read}, ACTION →
 *       {@link LedgerClient#postAction}, SIMULATED → {@link RunGuard#tryConsumeMessage}, UNROUTED → 503.</li>
 *   <li>{@link DecisionLog#record}: every decision after the token stage, with its stage, decision and code.</li>
 *   <li>Errors become error_response bodies with the code's HTTP status; nothing echoes the request or a token.</li>
 * </ul>
 */
public class ToolPipeline {
    final RunTokens tokens;
    final InputSchemas schemas;
    final RunGuard guard;
    final PolicyClient policy;
    final LedgerClient ledger;
    final DecisionLog log;
    final Clock clock;

    public ToolPipeline(RunTokens tokens, InputSchemas schemas, RunGuard guard, PolicyClient policy, LedgerClient ledger,
                        DecisionLog log, Clock clock) {
        this.tokens = tokens;
        this.schemas = schemas;
        this.guard = guard;
        this.policy = policy;
        this.ledger = ledger;
        this.log = log;
        this.clock = clock;
    }

    /**
     * Stage order: token → binding → schema → guard → (simulated budget | policy) → route. Every decision after the
     * token stage is logged. A routed call is logged ALLOW *before* the ledger sees it, so nothing executes without
     * its decision on record (log down → 503, not routed). A deny always stays a deny, even if logging it fails.
     */
    public ToolResult handle(ToolCall call) {
        RunClaims claims;
        try {
            claims = tokens.verify(call.bearer(), call.pathRunId(), call.tool());
        } catch (GatewayException e) {
            return error(e, call); // no trusted run or ns yet: nothing to attribute a log entry to
        }
        ToolRoute route = ToolRoutes.of(call.tool()); // in allowed_tools, so a §10 tool
        UUID actionId = uuid(call.body().get("action_id"));
        Decision d = new Decision(call, claims, actionId);

        JsonNode bodyRun = call.body().get("run_id");
        if (bodyRun == null || !bodyRun.isTextual() || !claims.runId().toString().equals(bodyRun.asText())) {
            return d.deny(Stage.BINDING, RunTokens.denied());
        }
        try {
            schemas.validate(call.tool(), call.body());
        } catch (GatewayException e) {
            return d.deny(Stage.SCHEMA, e);
        }
        try {
            guard.admit(claims.runId());
        } catch (GatewayException e) {
            return d.deny(Stage.GUARD, e);
        }

        if (route.kind() == RouteKind.SIMULATED) { // ADR-014: budgeted in every condition, no state change, no OPA
            if (!guard.tryConsumeMessage(claims.runId())) {
                return d.deny(Stage.POLICY, new GatewayException(ErrorCode.POLICY_DENIED, "counterparty message budget used up"));
            }
            if (!d.allow(null)) return d.unavailable();
            return new ToolResult(200, Contracts.MAPPER.createObjectNode().put("request_id", call.requestId().toString())
                    .put("status", "QUEUED").put("simulated", true));
        }

        String bundleHash = null;
        if ("full".equals(claims.controls()) && !"read".equals(route.risk())) {
            PolicyDecision p;
            try {
                p = policy.decide(runInput(claims), call.tool(), call.body());
            } catch (GatewayException e) {
                return d.deny(Stage.POLICY, e); // OPA down or unreadable: fail closed, never routed
            }
            bundleHash = p.bundleHash();
            if ("DENY".equals(p.decision())) {
                return d.deny(Stage.POLICY, new GatewayException(ErrorCode.POLICY_DENIED, "denied by policy"), bundleHash);
            }
            if ("REVIEW_REQUIRED".equals(p.decision())) { // held until OM-11; errors.json maps the code to 202
                return d.review(new GatewayException(ErrorCode.REVIEW_REQUIRED, "held for maker-checker review"), bundleHash);
            }
        }

        if (route.kind() == RouteKind.UNROUTED) {
            return d.deny(Stage.LEDGER, new GatewayException(ErrorCode.RETRYABLE_UNAVAILABLE, call.tool() + " unavailable"));
        }
        if (!d.allow(bundleHash)) return d.unavailable();
        LedgerResponse r;
        try {
            r = route.kind() == RouteKind.READ ? ledger.read(claims.ns(), route, call.body()) : ledger.postAction(claims.ns(), call.body());
        } catch (GatewayException e) {
            return error(e, call); // already logged as routed; the ledger committed nothing (G11)
        }
        return new ToolResult(r.status(), r.body());
    }

    /** OPA's view of the run: only verified token claims, never anything from the request body. */
    private static ObjectNode runInput(RunClaims c) {
        return Contracts.MAPPER.createObjectNode().put("run_id", c.runId().toString()).put("ns", c.ns().toString())
                .put("scenario_id", c.scenarioId()).put("agent_id", c.agentId()).put("controls", c.controls());
    }

    private static UUID uuid(JsonNode n) {
        if (n == null || !n.isTextual()) return null;
        try {
            UUID u = UUID.fromString(n.asText());
            return u.toString().equals(n.asText()) ? u : null; // canonical lowercase form only
        } catch (IllegalArgumentException e) {
            return null;
        }
    }

    static ToolResult error(GatewayException e, ToolCall call) {
        ObjectNode body = Contracts.MAPPER.valueToTree(new ErrorResponse(e.code(), e.detail(), call.requestId().toString(), null));
        return new ToolResult(e.code().httpStatus().orElseThrow(), body);
    }

    /** One call's decision, logged once with its stage. */
    private final class Decision {
        private final ToolCall call;
        private final RunClaims claims;
        private final UUID actionId;

        Decision(ToolCall call, RunClaims claims, UUID actionId) {
            this.call = call;
            this.claims = claims;
            this.actionId = actionId;
        }

        ToolResult deny(Stage stage, GatewayException e) {
            return deny(stage, e, null);
        }

        ToolResult deny(Stage stage, GatewayException e, String bundleHash) {
            record("DENY", e.code().name(), stage, bundleHash);
            return error(e, call);
        }

        ToolResult review(GatewayException e, String bundleHash) {
            record("REVIEW_REQUIRED", e.code().name(), Stage.POLICY, bundleHash);
            return error(e, call);
        }

        /** Logs ALLOW (stage routed); false if the log is unavailable, in which case nothing may be routed. */
        boolean allow(String bundleHash) {
            try {
                log.record(claims.ns(), entry("ALLOW", null, Stage.ROUTED, bundleHash));
                return true;
            } catch (GatewayException e) {
                return false;
            }
        }

        ToolResult unavailable() {
            return error(new GatewayException(ErrorCode.RETRYABLE_UNAVAILABLE, "decision log unavailable; nothing was routed"), call);
        }

        private void record(String decision, String code, Stage stage, String bundleHash) {
            try {
                log.record(claims.ns(), entry(decision, code, stage, bundleHash));
            } catch (GatewayException ignored) {
                // A deny stays a deny even if it couldn't be recorded; the miss shows as a log gap, never an ALLOW.
            }
        }

        private DecisionLogEntry entry(String decision, String code, Stage stage, String bundleHash) {
            return new DecisionLogEntry(UUID.randomUUID(), claims.runId(), call.tool(), actionId, decision, code,
                    claims.controls(), bundleHash, stage.wire(), clock.instant());
        }
    }
}
