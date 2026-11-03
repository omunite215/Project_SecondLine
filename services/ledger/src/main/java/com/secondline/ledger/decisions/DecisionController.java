package com.secondline.ledger.decisions;

import com.fasterxml.jackson.databind.JsonNode;
import com.secondline.contracts.CanonicalJson;
import com.secondline.contracts.ContractException;
import com.secondline.contracts.SchemaRegistry;
import com.secondline.contracts.generated.ErrorCode;
import com.secondline.ledger.LedgerException;
import com.secondline.ledger.ns.NamespaceRepository;
import java.time.Instant;
import java.util.UUID;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

/**
 * POST /internal/v1/ns/{ns}/decisions (ledger-internal.yaml append_decision, OM-05 G8). The entry must match
 * runs/decision_log_entry.schema.json and name a run registered in this LOADED ns; otherwise 422 / 403. Rows are
 * append-only (V006). An identical re-post is idempotent; the same decision_id with other content is a conflict.
 */
@RestController
public class DecisionController {
    private static final SchemaRegistry SCHEMAS = SchemaRegistry.load();

    private final NamespaceRepository namespaces;
    private final JdbcClient jdbc;

    public DecisionController(NamespaceRepository namespaces, JdbcClient jdbc) {
        this.namespaces = namespaces;
        this.jdbc = jdbc;
    }

    @PostMapping("/internal/v1/ns/{ns}/decisions")
    public ResponseEntity<Void> append(@PathVariable UUID ns, @RequestBody String body) {
        JsonNode e;
        String canonical;
        try {
            e = CanonicalJson.parse(body);
            canonical = CanonicalJson.canonicalize(e);
        } catch (ContractException x) {
            throw new LedgerException(ErrorCode.DOMAIN_INVALID, "body is not strict JSON");
        }
        if (!SCHEMAS.validate("runs/decision_log_entry.schema.json", e).isEmpty()) {
            throw new LedgerException(ErrorCode.DOMAIN_INVALID, "entry does not match decision_log_entry");
        }
        namespaces.requireLoaded(ns);
        UUID runId = UUID.fromString(e.get("run_id").asText());
        boolean registered = jdbc.sql("SELECT 1 FROM ledger.agent_runs WHERE ns = ? AND run_id = ?").params(ns, runId)
                .query(Integer.class).optional().isPresent();
        if (!registered) throw new LedgerException(ErrorCode.PERMISSION_DENIED, "run not registered in this namespace");
        UUID decisionId = UUID.fromString(e.get("decision_id").asText());
        int inserted = com.secondline.ledger.journal.Db.domain(() -> jdbc.sql("""
                        INSERT INTO ledger.policy_decisions (ns, decision_id, run_id, tool, action_id, decision, error_code,
                            controls, policy_bundle_hash, stage, at, entry)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (ns, decision_id) DO NOTHING""")
                .params(ns, decisionId, runId, e.get("tool").asText(), uuidOrNull(e, "action_id"), e.get("decision").asText(),
                        textOrNull(e, "error_code"), e.get("controls").asText(), textOrNull(e, "policy_bundle_hash"),
                        e.get("stage").asText(), java.sql.Timestamp.from(Instant.parse(e.get("at").asText())), canonical)
                .update());
        if (inserted == 0) {
            String stored = jdbc.sql("SELECT entry FROM ledger.policy_decisions WHERE ns = ? AND decision_id = ?")
                    .params(ns, decisionId).query(String.class).single();
            if (!stored.equals(canonical)) {
                throw new LedgerException(ErrorCode.IDEMPOTENCY_CONFLICT, "decision_id already recorded with other content");
            }
        }
        return ResponseEntity.status(201).build();
    }

    private static String textOrNull(JsonNode e, String f) {
        return e.hasNonNull(f) ? e.get(f).asText() : null;
    }

    private static UUID uuidOrNull(JsonNode e, String f) {
        return e.hasNonNull(f) ? UUID.fromString(e.get(f).asText()) : null;
    }
}
