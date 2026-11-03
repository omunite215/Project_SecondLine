package com.secondline.gateway.token;

import java.time.Instant;
import java.util.Set;
import java.util.UUID;

/** A verified run token: everything the pipeline may trust about the caller (G2, G3). */
public record RunClaims(UUID runId, UUID ns, String scenarioId, String agentId, String controls,
                        Set<String> allowedTools, Instant expiresAt) {
    public RunClaims {
        allowedTools = Set.copyOf(allowedTools);
    }
}
