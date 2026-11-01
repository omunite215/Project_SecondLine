package com.secondline.ledger.admin;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;

import com.fasterxml.jackson.databind.JsonNode;
import com.secondline.contracts.Contracts;
import com.secondline.contracts.SchemaRegistry;
import com.secondline.ledger.Bundles;
import com.secondline.ledger.LedgerDb;
import com.secondline.ledger.Services;
import java.nio.file.Path;
import java.util.UUID;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

/** OM-04 §7 §12 ADR-015 ADR-019 T-EVAL-03: the harness lifecycle over HTTP, as the runner (KG-15) will drive it. */
class OM_04_AdminApiTest {
    static final MockMvc MVC = Services.adminMvc();
    static final SchemaRegistry SCHEMAS = SchemaRegistry.load();

    @BeforeAll
    static void schema() {
        LedgerDb.migrate();
    }

    static MvcResult perform(org.springframework.test.web.servlet.RequestBuilder r) throws Exception {
        return MVC.perform(r).andReturn();
    }

    static JsonNode body(MvcResult r) throws Exception {
        String s = r.getResponse().getContentAsString();
        return s.isEmpty() ? null : Contracts.MAPPER.readTree(s);
    }

    static UUID create() throws Exception {
        MvcResult r = perform(post("/admin/v1/ns"));
        assertThat(r.getResponse().getStatus()).isEqualTo(201);
        return UUID.fromString(body(r).get("ns").asText());
    }

    static MvcResult load(UUID ns, String json) throws Exception {
        return perform(post("/admin/v1/ns/" + ns + ":load").contentType(MediaType.APPLICATION_JSON).content(json));
    }

    static void assertError(MvcResult r, int status, String code) throws Exception {
        assertThat(r.getResponse().getStatus()).isEqualTo(status);
        JsonNode b = body(r);
        assertThat(b.get("error_code").asText()).isEqualTo(code);
        assertThat(SCHEMAS.validate("error_response.schema.json", b)).isEmpty();
    }

    @Test
    void OM_04_createLoadExportHashRoundTrip() throws Exception {
        UUID ns = create();
        MvcResult loaded = load(ns, Bundles.minimal().toString());
        assertThat(loaded.getResponse().getStatus()).isEqualTo(201);
        JsonNode vector = Contracts.MAPPER.readTree(
                Path.of(System.getProperty("contracts.root"), "test-vectors/state_hash/minimal.json").toFile());
        // The runner sees the Python-computed golden hash straight from the API.
        assertThat(body(loaded).get("state_hash").asText()).isEqualTo(vector.get("state_hash").asText());
        assertThat(body(loaded).get("snapshot_hash").asText()).isEqualTo(vector.get("snapshot_hash").asText());
        JsonNode export = body(perform(get("/admin/v1/ns/" + ns + "/export")));
        assertThat(SCHEMAS.validate("scenario/ns_export.schema.json", export)).isEmpty();
        assertThat(body(perform(get("/admin/v1/ns/" + ns + "/state-hash")))).isEqualTo(body(loaded));
        assertThat(load(ns, Bundles.minimal().toString()).getResponse().getStatus()).isEqualTo(200);
    }

    @Test
    void OM_04_differentBundleIsIdempotencyConflict() throws Exception {
        UUID ns = create();
        load(ns, Bundles.minimal().toString());
        assertError(load(ns, Bundles.rich().toString()), 409, "IDEMPOTENCY_CONFLICT");
    }

    @Test
    void OM_04_retiredNamespaceIsDeniedButKept() throws Exception {
        UUID ns = create();
        load(ns, Bundles.minimal().toString());
        assertThat(perform(delete("/admin/v1/ns/" + ns)).getResponse().getStatus()).isEqualTo(204);
        assertError(perform(get("/admin/v1/ns/" + ns + "/export")), 403, "PERMISSION_DENIED");
        assertError(perform(get("/admin/v1/ns/" + ns + "/state-hash")), 403, "PERMISSION_DENIED");
        assertError(load(ns, Bundles.minimal().toString()), 403, "PERMISSION_DENIED");
        assertError(perform(delete("/admin/v1/ns/" + UUID.randomUUID())), 403, "PERMISSION_DENIED");
        assertThat(LedgerDb.query(LedgerDb.migrator(), "SELECT count(*) FROM ledger.journal_headers WHERE ns = ?", ns))
                .isEqualTo("1");  // ADR-019: retiring never deletes ledger rows
    }

    @Test
    void OM_04_bodiesAreParsedStrictly() throws Exception {
        UUID ns = create();
        String dup = Bundles.minimal().toString().replaceFirst("\\{", "{\"as_of\":\"2026-01-01\",");
        assertError(load(ns, dup), 422, "DOMAIN_INVALID");
        assertError(load(ns, Bundles.minimal().toString() + " {}"), 422, "DOMAIN_INVALID");
        assertError(load(ns, Bundles.with(b -> b.put("truth_ref", "internal:oracle/x")).toString()), 422, "DOMAIN_INVALID");
        assertThat(LedgerDb.query(LedgerDb.app(), "SELECT status FROM ledger.namespaces WHERE ns = ?", ns)).isEqualTo("EMPTY");
    }

    @Test
    void OM_04_everyFailureIsATypedErrorResponse() throws Exception {
        UUID ns = create();
        assertError(perform(post("/admin/v1/ns/" + ns + ":load").contentType(MediaType.APPLICATION_JSON)), 422, "DOMAIN_INVALID");
        assertError(perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put("/admin/v1/ns/" + ns + "/export")),
                422, "DOMAIN_INVALID");
        assertError(perform(get("/admin/v1/no-such-route")), 422, "DOMAIN_INVALID");
        // Anything unforeseen leaves as a typed 503 with a fixed message, never a stack trace or a value.
        var r = new com.secondline.ledger.web.ErrorAdvice().unexpected(new IllegalStateException("secret detail trd_0000B001"));
        assertThat(r.getStatusCode().value()).isEqualTo(503);
        assertThat(r.getBody().get("error_code").asText()).isEqualTo("RETRYABLE_UNAVAILABLE");
        assertThat(r.getBody().toString()).doesNotContain("secret").doesNotContain("trd_");
        assertThat(SCHEMAS.validate("error_response.schema.json", r.getBody())).isEmpty();
    }

    static MvcResult run(String json) throws Exception {
        return perform(post("/admin/v1/runs").contentType(MediaType.APPLICATION_JSON).content(json));
    }

    @Test
    void OM_04_registerRun() throws Exception {
        UUID ns = create();
        load(ns, Bundles.minimal().toString());
        String ok = "{\"ns\":\"" + ns + "\",\"controls\":\"full\",\"agent_id\":\"agt_00000001\",\"manifest_ref\":\"experiments/manifests/p1.json\"}";
        MvcResult r = run(ok);
        assertThat(r.getResponse().getStatus()).isEqualTo(201);
        assertThat(body(r).get("controls").asText()).isEqualTo("full");
        assertError(run(ok.replace("\"full\"", "\"none\"")), 422, "DOMAIN_INVALID");
        assertError(run(ok.replace("experiments/manifests/p1.json", "data/generated/eval/truth/x.json")), 422, "DOMAIN_INVALID");
        assertError(run(ok.replace("}", ",\"budget\":\"9\"}")), 422, "DOMAIN_INVALID");
        assertError(run(ok.replace("\"agt_00000001\"", "1")), 422, "DOMAIN_INVALID");
        assertError(run(ok.replace(ns.toString(), UUID.randomUUID().toString())), 403, "PERMISSION_DENIED");
        UUID empty = create();
        assertError(run(ok.replace(ns.toString(), empty.toString())), 403, "PERMISSION_DENIED");
    }

    @Test
    void OM_04_adminResponsesMatchTheContract() throws Exception {
        UUID ns = create();
        JsonNode loaded = body(load(ns, Bundles.minimal().toString()));
        // LoadResult / StateHash (inline in openapi/ledger-admin.yaml): exactly these four fields.
        assertThat(loaded.size()).isEqualTo(4);
        assertThat(loaded.get("ns").asText()).isEqualTo(ns.toString());
        assertThat(loaded.get("state_hash").asText()).matches("^sha256:[0-9a-f]{64}$");
        assertThat(loaded.get("snapshot_hash").asText()).matches("^sha256:[0-9a-f]{64}$");
        assertThat(loaded.get("state_version").isIntegralNumber()).isTrue();
    }
}
