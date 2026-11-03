package com.secondline.gateway.client;

import java.time.Instant;
import java.util.UUID;

/** runs/decision_log_entry.schema.json (G8): one gateway decision, including every deny and the stage it came from. */
public record DecisionLogEntry(
        UUID decisionId,
        UUID runId,
        String tool,
        UUID actionId,
        String decision,
        String errorCode,
        String controls,
        String policyBundleHash,
        String stage,
        Instant at) {}
