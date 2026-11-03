package com.secondline.ledger.decisions;

import static com.secondline.ledger.LedgerDb.app;
import static com.secondline.ledger.LedgerDb.exec;
import static com.secondline.ledger.LedgerDb.migrator;
import static com.secondline.ledger.LedgerDb.query;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.secondline.contracts.Contracts;
import com.secondline.contracts.SchemaRegistry;
import com.secondline.ledger.Bundles;
import com.secondline.ledger.LedgerDb;
import com.secondline.ledger.Services;
import java.sql.SQLException;
import java.util.UUID;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

/** OM-05 Task 5 G8 §8 §12: the gateway's decision log, stored by the ledger, append-only. */
class OM_05_DecisionLogTest {
    static final MockMvc ADMIN = Services.adminMvc();
    static final MockMvc MVC = Services.decisionsMvc();
    static final SchemaRegistry SCHEMAS = SchemaRegistry.load();

    @BeforeAll
    static void schema() {
        LedgerDb.migrate();
    }

    /** A LOADED ns with one registered run; returns {ns, run_id}. */
    static UUID[] loadedRun() throws Exception {
        JsonNode created = json(ADMIN.perform(post("/admin/v1/ns")).andReturn());
        UUID ns = UUID.fromString(created.get("ns").asText());
        ADMIN.perform(post("/admin/v1/ns/" + ns + ":load").contentType(MediaType.APPLICATION_JSON).content(Bundles.minimal().toString()));
        JsonNode run = json(ADMIN.perform(post("/admin/v1/runs").contentType(MediaType.APPLICATION_JSON).content(
                Contracts.MAPPER.createObjectNode().put("ns", ns.toString()).put("controls", "full").put("agent_id", "agt_00000001")
                        .put("manifest_ref", "experiments/manifests/pilot-001.json").toString())).andReturn());
        return new UUID[] {ns, UUID.fromString(run.get("run_id").asText())};
    }

    static JsonNode json(MvcResult r) throws Exception {
        String s = r.getResponse().getContentAsString();
        return s.isEmpty() ? null : Contracts.MAPPER.readTree(s);
    }

    static ObjectNode entry(UUID run) {
        return Contracts.MAPPER.createObjectNode().put("decision_id", UUID.randomUUID().toString()).put("run_id", run.toString())
                .put("tool", "propose_adjustment").put("decision", "DENY").put("error_code", "POLICY_DENIED")
                .put("controls", "full").put("policy_bundle_hash", "sha256:" + "c".repeat(64)).put("stage", "policy")
                .put("at", "2026-11-03T12:00:00.000Z");
    }

    static MvcResult send(UUID ns, JsonNode e) throws Exception {
        return MVC.perform(post("/internal/v1/ns/" + ns + "/decisions").contentType(MediaType.APPLICATION_JSON).content(e.toString())).andReturn();
    }

    static void error(MvcResult r, int status, String code) throws Exception {
        assertThat(r.getResponse().getStatus()).isEqualTo(status);
        JsonNode b = json(r);
        assertThat(b.get("error_code").asText()).isEqualTo(code);
        assertThat(SCHEMAS.validate("error_response.schema.json", b)).isEmpty();
    }

    @Test
    void OM_05_decisionStoredForARegisteredRun() throws Exception {
        UUID[] nr = loadedRun();
        ObjectNode e = entry(nr[1]);
        assertThat(send(nr[0], e).getResponse().getStatus()).isEqualTo(201);
        assertThat(query(app(), "SELECT decision || '/' || stage || '/' || error_code FROM ledger.policy_decisions WHERE ns = ? AND decision_id = ?::uuid",
                nr[0], e.get("decision_id").asText())).isEqualTo("DENY/policy/POLICY_DENIED");
    }

    @Test
    void OM_05_identicalRepostIsIdempotent() throws Exception {
        UUID[] nr = loadedRun();
        ObjectNode e = entry(nr[1]);
        send(nr[0], e);
        assertThat(send(nr[0], e).getResponse().getStatus()).isEqualTo(201);
        assertThat(query(app(), "SELECT count(*) FROM ledger.policy_decisions WHERE ns = ?", nr[0])).isEqualTo("1");
    }

    @Test
    void OM_05_sameDecisionIdDifferentEntryIsConflict() throws Exception {
        UUID[] nr = loadedRun();
        ObjectNode e = entry(nr[1]);
        send(nr[0], e);
        ObjectNode changed = e.deepCopy();
        changed.put("decision", "ALLOW").remove("error_code");
        changed.put("stage", "routed");
        error(send(nr[0], changed), 409, "IDEMPOTENCY_CONFLICT");
        assertThat(query(app(), "SELECT decision FROM ledger.policy_decisions WHERE ns = ?", nr[0])).isEqualTo("DENY");
    }

    @Test
    void OM_05_unknownNsOrUnregisteredRunIs403() throws Exception {
        UUID[] nr = loadedRun();
        error(send(UUID.randomUUID(), entry(nr[1])), 403, "PERMISSION_DENIED");
        error(send(nr[0], entry(UUID.randomUUID())), 403, "PERMISSION_DENIED");
        UUID[] other = loadedRun();
        error(send(other[0], entry(nr[1])), 403, "PERMISSION_DENIED"); // a run of another ns
    }

    @Test
    void OM_05_schemaInvalidEntryIs422() throws Exception {
        UUID[] nr = loadedRun();
        ObjectNode badStage = entry(nr[1]);
        badStage.put("stage", "somewhere");
        error(send(nr[0], badStage), 422, "DOMAIN_INVALID");
        ObjectNode graderCode = entry(nr[1]);
        graderCode.put("error_code", "ORACLE_MISMATCH");
        error(send(nr[0], graderCode), 422, "DOMAIN_INVALID");
        ObjectNode extra = entry(nr[1]);
        extra.put("root_cause", "B7");
        error(send(nr[0], extra), 422, "DOMAIN_INVALID");
        assertThat(query(app(), "SELECT count(*) FROM ledger.policy_decisions WHERE ns = ?", nr[0])).isEqualTo("0");
    }

    @Test
    void OM_05_decisionsAreAppendOnly() throws Exception {
        UUID[] nr = loadedRun();
        send(nr[0], entry(nr[1]));
        for (String sql : new String[] {"UPDATE ledger.policy_decisions SET decision = 'ALLOW' WHERE ns = ?",
                "DELETE FROM ledger.policy_decisions WHERE ns = ?"}) {
            assertThatThrownBy(() -> exec(app(), sql, nr[0])).isInstanceOf(SQLException.class).extracting("SQLState").isEqualTo("42501");
            assertThatThrownBy(() -> exec(migrator(), sql, nr[0])).isInstanceOf(SQLException.class).extracting("SQLState").isEqualTo("P0001");
        }
    }
}
