package com.secondline.gateway.token;

import java.util.List;
import java.util.UUID;

/** What a run token grants (G2): one run in one ns, for one scenario, agent and control condition. */
public record RunGrant(UUID runId, UUID ns, String scenarioId, String agentId, String controls, List<String> allowedTools) {
    public RunGrant {
        allowedTools = List.copyOf(allowedTools);
    }
}
