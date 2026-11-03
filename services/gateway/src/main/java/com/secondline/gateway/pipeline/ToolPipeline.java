package com.secondline.gateway.pipeline;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.secondline.contracts.Contracts;
import com.secondline.contracts.ErrorResponse;
import com.secondline.contracts.generated.ErrorCode;
import com.secondline.gateway.GatewayException;
import com.secondline.gateway.client.DecisionLog;
import com.secondline.gateway.client.DecisionLogEntry;
import com.secondline.gateway.client.LedgerClient;
import com.secondline.gateway.client.LedgerResponse;
import com.secondline.gateway.client.PolicyClient;
import com.secondline.gateway.client.PolicyDecision;
import com.secondline.gateway.guard.RunGuard;
import com.secondline.gateway.route.RouteKind;
import com.secondline.gateway.route.ToolRoute;
import com.secondline.gateway.route.ToolRoutes;
import com.secondline.gateway.schema.InputSchemas;
import com.secondline.gateway.token.RunClaims;
import com.secondline.gateway.token.RunTokens;
import io.micrometer.core.instrument.MeterRegistry;
import java.time.Clock;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * The gateway's policy enforcement point (OM-05 Task 4, §8 §11, ADR-013, ADR-014). {@link #handle} (learn card;
 * written by Claude at Om's request, 2026-11-03), spec {@code OM_05_PipelineTest}.
 *
 * <p>Stage order: token → call budget → body → binding → schema → halt (monitor/full only) → (simulated C_msg |
 * OPA in full for non-read tools) → route. Decisions (§8 step 3 "logs all decisions, including denies"):
 * <ul>
 *   <li>token-stage denials have no trusted ns for the ledger's ns-scoped log, so they're audit-logged by the gateway
 *       and counted ({@code gateway.token_denied}), never dropped;</li>
 *   <li>every later decision goes to the ledger decision log once its outcome is known: ALLOW at stage routed only
 *       after the ledger answered 2xx (decision_log_entry contract), DENY at stage ledger for a ledger refusal,
 *       outage or a 2xx that fails its output schema;</li>
 *   <li>a deny always stays a deny, whatever happens while recording it.</li>
 * </ul>
 * OPA and the ledger only ever get ns, controls and run identity from the verified token, never from the body.
 */
public class ToolPipeline {
    private static final Logger AUDIT = LoggerFactory.getLogger("com.secondline.gateway.audit");
    private static final Set<String> TOOLS = ToolRoutes.all().stream().map(ToolRoute::tool).collect(Collectors.toUnmodifiableSet());

    final RunTokens tokens;
    final InputSchemas schemas;
    final RunGuard guard;
    final PolicyClient policy;
    final LedgerClient ledger;
    final DecisionLog log;
    final Clock clock;
    final MeterRegistry meters;

    public ToolPipeline(RunTokens tokens, InputSchemas schemas, RunGuard guard, PolicyClient policy, LedgerClient ledger,
                        DecisionLog log, Clock clock, MeterRegistry meters) {
        this.tokens = tokens;
        this.schemas = schemas;
        this.guard = guard;
        this.policy = policy;
        this.ledger = ledger;
        this.log = log;
        this.clock = clock;
        this.meters = meters;
    }

    public ToolResult handle(ToolCall call) {
        RunClaims claims;
        try {
            claims = tokens.verify(call.bearer(), call.pathRunId(), call.tool());
        } catch (GatewayException e) {
            String tool = TOOLS.contains(call.tool()) ? call.tool() : "unknown";
            meters.counter("gateway.token_denied", "tool", tool).increment();
            AUDIT.warn("decision=DENY stage=token tool={} request_id={}", tool, call.requestId()); // never the token
            return error(e, call, null);
        }
        Decision d = new Decision(call, claims);
        try {
            guard.admit(claims.runId()); // every verified call counts, valid or not (a runaway can't dodge the cap)
        } catch (GatewayException e) {
            return d.deny(Stage.GUARD, e);
        }
        if (call.body() == null) {
            return d.deny(Stage.SCHEMA, new GatewayException(ErrorCode.DOMAIN_INVALID,
                    "request body must be one JSON object (no duplicate keys, no floats)"));
        }
        JsonNode bodyRun = call.body().get("run_id");
        if (bodyRun == null || !bodyRun.isTextual() || !claims.runId().toString().equals(bodyRun.asText())) {
            return d.deny(Stage.BINDING, RunTokens.denied());
        }
        try {
            schemas.validate(call.tool(), call.body());
        } catch (GatewayException e) {
            return d.deny(Stage.SCHEMA, e);
        }
        if (!"off".equals(claims.controls()) && guard.halted(claims.runId())) { // ADR-014: no kill switch in B
            return d.deny(Stage.GUARD, new GatewayException(ErrorCode.RUN_HALTED, "run halted"));
        }

        ToolRoute route = ToolRoutes.of(call.tool());
        if (route.kind() == RouteKind.SIMULATED) { // ADR-014: budgeted in every condition, no state change, no OPA
            boolean ok;
            try {
                ok = guard.tryConsumeMessage(claims.runId(), () -> breakCount(claims));
            } catch (GatewayException e) {
                return d.deny(Stage.POLICY, e); // budget unknown → fail closed
            }
            if (!ok) return d.deny(Stage.POLICY, new GatewayException(ErrorCode.POLICY_DENIED, "counterparty message budget used up"));
            d.allow(null);
            return new ToolResult(200, Contracts.MAPPER.createObjectNode().put("request_id", call.requestId().toString())
                    .put("status", "QUEUED").put("simulated", true), claims.runId());
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
            if ("REVIEW_REQUIRED".equals(p.decision())) {
                // Not routed. §8 step 4 (persist digest + versions, maker-checker) is OM-11's approval store; until then
                // the decision log entry (action_id + REVIEW_REQUIRED) is the record. errors.json maps the code to 202.
                return d.review(new GatewayException(ErrorCode.REVIEW_REQUIRED, "held for maker-checker review"), bundleHash);
            }
        }

        if (route.kind() == RouteKind.UNROUTED) {
            return d.deny(Stage.LEDGER, new GatewayException(ErrorCode.RETRYABLE_UNAVAILABLE, call.tool() + " unavailable"));
        }
        LedgerResponse r;
        try {
            r = route.kind() == RouteKind.READ ? ledger.read(claims.ns(), route, call.body()) : ledger.postAction(claims.ns(), call.body());
        } catch (GatewayException e) {
            // A write may or may not have committed: only a retry with the same idempotency_key is safe (§8 step 6).
            GatewayException unknown = route.kind() == RouteKind.READ ? e : new GatewayException(ErrorCode.RETRYABLE_UNAVAILABLE,
                    "ledger outcome unknown; retry with the same idempotency_key");
            return d.deny(Stage.LEDGER, unknown, bundleHash);
        }
        if (r.status() >= 400) { // a contract error_response from the ledger: passed through, recorded as its DENY
            d.record("DENY", r.body().path("error_code").asText(null), Stage.LEDGER, bundleHash);
            return new ToolResult(r.status(), r.body(), claims.runId());
        }
        if (!schemas.outputMatches(call.tool(), r.body())) { // defence in depth: nothing off-contract reaches the agent
            return d.deny(Stage.LEDGER, new GatewayException(ErrorCode.RETRYABLE_UNAVAILABLE,
                    "ledger answer did not match its contract"), bundleHash);
        }
        d.allow(bundleHash);
        return new ToolResult(r.status(), r.body(), claims.runId());
    }

    /** ADR-014 C_msg placeholder: one message per break in the run, from the ledger's list_breaks. */
    private int breakCount(RunClaims claims) {
        ObjectNode q = Contracts.MAPPER.createObjectNode().put("run_id", claims.runId().toString());
        LedgerResponse r = ledger.read(claims.ns(), ToolRoutes.of("list_breaks"), q);
        JsonNode breaks = r.body().get("breaks");
        if (r.status() != 200 || breaks == null || !breaks.isArray()) {
            throw new GatewayException(ErrorCode.RETRYABLE_UNAVAILABLE, "message budget unavailable");
        }
        return breaks.size();
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

    static ToolResult error(GatewayException e, ToolCall call, UUID verifiedRunId) {
        ObjectNode body = Contracts.MAPPER.valueToTree(new ErrorResponse(e.code(), e.detail(), call.requestId().toString(), null));
        return new ToolResult(e.code().httpStatus().orElseThrow(), body, verifiedRunId);
    }

    /** One verified call's decision record. */
    private final class Decision {
        private final ToolCall call;
        private final RunClaims claims;
        private final UUID actionId;

        Decision(ToolCall call, RunClaims claims) {
            this.call = call;
            this.claims = claims;
            this.actionId = call.body() == null ? null : uuid(call.body().get("action_id"));
        }

        ToolResult deny(Stage stage, GatewayException e) {
            return deny(stage, e, null);
        }

        ToolResult deny(Stage stage, GatewayException e, String bundleHash) {
            record("DENY", e.code().name(), stage, bundleHash);
            return error(e, call, claims.runId());
        }

        ToolResult review(GatewayException e, String bundleHash) {
            record("REVIEW_REQUIRED", e.code().name(), Stage.POLICY, bundleHash);
            return error(e, call, claims.runId());
        }

        void allow(String bundleHash) {
            record("ALLOW", null, Stage.ROUTED, bundleHash);
        }

        /**
         * Best effort, after the outcome is fixed: a recording failure never changes the answer (a deny stays a deny;
         * an executed action's authoritative record is the ledger's receipt, OM-14). A miss is counted and audit-logged.
         */
        void record(String decision, String code, Stage stage, String bundleHash) {
            try {
                log.record(claims.ns(), new DecisionLogEntry(UUID.randomUUID(), claims.runId(), call.tool(), actionId, decision,
                        code, claims.controls(), bundleHash, stage.wire(), clock.instant()));
            } catch (RuntimeException e) {
                meters.counter("gateway.decision_log_missed", "stage", stage.wire()).increment();
                AUDIT.error("decision log write failed decision={} stage={} run_id={} request_id={}", decision, stage.wire(),
                        claims.runId(), call.requestId());
            }
        }
    }
}
