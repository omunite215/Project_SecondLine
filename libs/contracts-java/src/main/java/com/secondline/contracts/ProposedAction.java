package com.secondline.contracts;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import com.secondline.contracts.generated.ActionType;
import com.secondline.contracts.generated.ReasonCode;
import java.util.List;

/**
 * actions/proposed_action.schema.json. Validate the raw document with {@link SchemaRegistry} first;
 * `parameters` stays a JsonNode because its shape depends on `type` (actions/parameters/*).
 */
public record ProposedAction(
        @JsonProperty("action_id") String actionId,
        @JsonProperty("run_id") String runId,
        @JsonProperty("break_id") String breakId,
        @JsonProperty("request_id") String requestId,
        @JsonProperty("tool_schema_version") String toolSchemaVersion,
        @JsonProperty("type") ActionType type,
        @JsonProperty("reason_code") ReasonCode reasonCode,
        @JsonProperty("parameters") JsonNode parameters,
        @JsonProperty("evidence_refs") List<EvidenceRef> evidenceRefs,
        @JsonProperty("expected_state_version") long expectedStateVersion,
        @JsonProperty("idempotency_key") String idempotencyKey,
        /** Untrusted (C6): never authorises anything and is not part of the digest. */
        @JsonProperty("agent_explanation") String agentExplanation) {

    public String actionDigest() {
        return ActionDigest.of(Contracts.MAPPER.valueToTree(this));
    }
}
