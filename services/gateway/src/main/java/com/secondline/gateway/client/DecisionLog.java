package com.secondline.gateway.client;

import com.fasterxml.jackson.databind.node.ObjectNode;
import com.secondline.contracts.Contracts;
import com.secondline.contracts.SchemaRegistry;
import java.time.temporal.ChronoUnit;
import java.util.UUID;

/**
 * Persists every decision through the ledger (G8). An entry that doesn't match its schema is never sent; the
 * caller gets RETRYABLE_UNAVAILABLE, so a decision that can't be recorded is a decision that didn't happen.
 */
public class DecisionLog {
    private final LedgerClient ledger;
    private final SchemaRegistry schemas;

    public DecisionLog(LedgerClient ledger, SchemaRegistry schemas) {
        this.ledger = ledger;
        this.schemas = schemas;
    }

    public void record(UUID ns, DecisionLogEntry entry) {
        ObjectNode json = toJson(entry);
        if (!schemas.validate("runs/decision_log_entry.schema.json", json).isEmpty()) throw Http.unavailable("decision log", null);
        LedgerResponse r = ledger.appendDecision(ns, json);
        if (r.status() >= 300) throw Http.unavailable("decision log", null);
    }

    /** Explicit, so absent optionals are omitted (no nulls) and `at` is a utc_timestamp (ms, Z). */
    static ObjectNode toJson(DecisionLogEntry e) {
        ObjectNode j = Contracts.MAPPER.createObjectNode();
        j.put("decision_id", e.decisionId().toString());
        j.put("run_id", e.runId().toString());
        j.put("tool", e.tool());
        if (e.actionId() != null) j.put("action_id", e.actionId().toString());
        j.put("decision", e.decision());
        if (e.errorCode() != null) j.put("error_code", e.errorCode());
        j.put("controls", e.controls());
        if (e.policyBundleHash() != null) j.put("policy_bundle_hash", e.policyBundleHash());
        j.put("stage", e.stage());
        j.put("at", e.at().truncatedTo(ChronoUnit.MILLIS).toString());
        return j;
    }
}
