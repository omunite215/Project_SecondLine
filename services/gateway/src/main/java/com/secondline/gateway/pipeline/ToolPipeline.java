package com.secondline.gateway.pipeline;

import com.secondline.gateway.client.DecisionLog;
import com.secondline.gateway.client.LedgerClient;
import com.secondline.gateway.client.PolicyClient;
import com.secondline.gateway.guard.RunGuard;
import com.secondline.gateway.schema.InputSchemas;
import com.secondline.gateway.token.RunTokens;
import java.time.Clock;

/**
 * The gateway's policy enforcement point (OM-05 Task 4, §8 §11, ADR-013, ADR-014).
 *
 * <p><b>[Om writes]</b> {@link #handle}. The spec is {@code OM_05_PipelineTest}. The design is yours: the stage
 * order, which stage runs in which control condition, and how every failure maps to a typed, fail-closed answer.
 * The building blocks (all tested in Task 3):
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

    public ToolResult handle(ToolCall call) {
        throw new UnsupportedOperationException("[Om writes] OM-05 Task 4");
    }
}
