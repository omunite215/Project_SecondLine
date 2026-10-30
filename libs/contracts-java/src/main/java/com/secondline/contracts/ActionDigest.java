package com.secondline.contracts;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.JsonNodeFactory;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Set;

/**
 * ADR-011 action digest, shared by approvals (OM-11) and idempotency (OM-09). The field set is the
 * contract's `x-action-digest` in actions/proposed_action.schema.json; Kunal's audit-verifier
 * recomputes it from the same list. Per-request ids, the idempotency key and the untrusted
 * agent_explanation (C6) are excluded, so a retry of the same action digests the same.
 */
public final class ActionDigest {
    public static final List<String> INCLUDED = List.of(
            "run_id", "break_id", "tool_schema_version", "type", "reason_code",
            "parameters", "evidence_refs", "expected_state_version");

    private static final Set<String> TEXT_FIELDS = Set.of("run_id", "break_id", "tool_schema_version", "type", "reason_code");
    private static final Comparator<JsonNode> REF_ORDER = Comparator
            .<JsonNode, String>comparing(r -> r.get("record_id").textValue()) // UTF-16 order, as JCS keys
            .thenComparingLong(r -> r.get("version").longValue());

    private ActionDigest() {}

    /** Digest of a ProposedAction document. Any missing or mistyped bound field throws: no digest, no mutation. */
    public static String of(JsonNode action) {
        return Digests.sha256Canonical(bound(action));
    }

    /** The exact object that is canonicalised and hashed (exposed for the golden vectors). */
    public static ObjectNode bound(JsonNode action) {
        ObjectNode bound = JsonNodeFactory.instance.objectNode();
        for (String field : INCLUDED) {
            JsonNode value = action.get(field);
            if (value == null || value.isNull()) {
                throw new ContractException("action_digest: missing " + field);
            }
            bound.set(field, value);
        }
        for (String field : TEXT_FIELDS) {
            require(bound.get(field).isTextual(), field + " is not a string");
        }
        require(bound.get("parameters").isObject(), "parameters is not an object");
        require(bound.get("expected_state_version").isIntegralNumber(), "expected_state_version is not an integer");
        require(bound.get("evidence_refs").isArray(), "evidence_refs is not an array");
        List<JsonNode> refs = new ArrayList<>();
        for (JsonNode r : bound.get("evidence_refs")) {
            require(r.isObject() && r.size() == 2 && r.path("record_id").isTextual() && r.path("version").isIntegralNumber(),
                    "evidence_ref must be exactly {record_id: string, version: integer}: " + r);
            refs.add(r);
        }
        refs.sort(REF_ORDER);
        ArrayNode sorted = bound.arrayNode();
        refs.forEach(sorted::add);
        bound.set("evidence_refs", sorted);
        return bound;
    }

    private static void require(boolean ok, String message) {
        if (!ok) {
            throw new ContractException("action_digest: " + message);
        }
    }
}
