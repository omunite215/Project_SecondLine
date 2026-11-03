package com.secondline.ledger.read;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.JsonNode;
import com.secondline.contracts.SchemaRegistry;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.yaml.snakeyaml.Yaml;

/**
 * OM-04 §10 REQ-001: every GET in openapi/ledger-internal.yaml (minus OM-08's routes) answers 200 on a loaded
 * namespace with a body that validates against the tool output schema the contract names. A new path without
 * a case here fails the test, so the contract and the controller can't drift apart.
 */
class OM_04_ReadContractTest {
    /** One concrete call per contract path, all resolvable in Bundles.rich(). */
    static final Map<String, String> PATHS = new LinkedHashMap<>();

    static {
        PATHS.put("/internal/v1/ns/{ns}/breaks", "/breaks");
        PATHS.put("/internal/v1/ns/{ns}/breaks/{break_id}", "/breaks/brk_0000F001");
        PATHS.put("/internal/v1/ns/{ns}/trades/{trade_id}", "/trades/trd_0000B001?as_of_version=0");
        PATHS.put("/internal/v1/ns/{ns}/trades/{trade_id}/bookings", "/trades/trd_0000B001/bookings");
        PATHS.put("/internal/v1/ns/{ns}/trades/{trade_id}/settlement", "/trades/trd_0000B001/settlement");
        PATHS.put("/internal/v1/ns/{ns}/positions", "/positions?isin=XS0000000012");
        PATHS.put("/internal/v1/ns/{ns}/custodian-statement", "/custodian-statement?as_of_date=2026-03-02");
        PATHS.put("/internal/v1/ns/{ns}/corporate-actions", "/corporate-actions?isin=XS0000000012");
        PATHS.put("/internal/v1/ns/{ns}/evidence/{record_id}", "/evidence/evd_0000E003");
        PATHS.put("/internal/v1/ns/{ns}/reference-data/{record_id}", "/reference-data/isn_XS0000000012");
        PATHS.put("/internal/v1/ns/{ns}/fx", "/fx?base=EUR&quote=USD&as_of_date=2026-03-02");
    }

    /** Routes other cards build (OM-08 actions; /state is the gateway's state probe, also OM-08). */
    static final java.util.Set<String> LATER = java.util.Set.of("/internal/v1/ns/{ns}/actions", "/internal/v1/ns/{ns}/state");

    @SuppressWarnings("unchecked")
    static Map<String, Object> contractPaths() throws Exception {
        Path f = Path.of(System.getProperty("contracts.root"), "openapi/ledger-internal.yaml");
        Map<String, Object> doc = new Yaml().load(Files.readString(f));
        return (Map<String, Object>) doc.get("paths");
    }

    /** Property names the 200 schema of a contract path declares (at any depth). */
    @SuppressWarnings("unchecked")
    static java.util.Set<String> declaredNames(String contractPath) throws Exception {
        Map<String, Object> ok = (Map<String, Object>) ((Map<String, Object>) ((Map<String, Object>) ((Map<String, Object>)
                contractPaths().get(contractPath)).get("get")).get("responses")).get("200");
        String ref = (String) ((Map<String, Object>) ((Map<String, Object>) ((Map<String, Object>) ok.get("content"))
                .get("application/json")).get("schema")).get("$ref");
        JsonNode schema = com.secondline.contracts.Contracts.MAPPER.readTree(
                Path.of(System.getProperty("contracts.root"), ref.replace("../", "")).toFile());
        java.util.Set<String> out = new java.util.HashSet<>();
        java.util.ArrayDeque<JsonNode> todo = new java.util.ArrayDeque<>(java.util.List.of(schema));
        while (!todo.isEmpty()) {
            JsonNode n = todo.pop();
            if (n.has("properties")) n.get("properties").fieldNames().forEachRemaining(out::add);
            n.forEach(todo::push);
        }
        return out;
    }

    @Test
    @SuppressWarnings("unchecked")
    void OM_04_everyContractReadAnswersWithItsSchema() throws Exception {
        OM_04_ReadApiTest.load();
        SchemaRegistry schemas = SchemaRegistry.load();
        Map<String, Object> paths = contractPaths();
        for (Map.Entry<String, Object> p : paths.entrySet()) {
            if (LATER.contains(p.getKey())) continue;
            // Only read routes: a path without GET is a write (actions, decisions), tested where it's built.
            if (!((Map<String, Object>) p.getValue()).containsKey("get")) continue;
            assertThat(PATHS).as("no test call for contract path " + p.getKey()).containsKey(p.getKey());
            Map<String, Object> getOp = (Map<String, Object>) ((Map<String, Object>) p.getValue()).get("get");
            Map<String, Object> ok = (Map<String, Object>) ((Map<String, Object>) getOp.get("responses")).get("200");
            String ref = (String) ((Map<String, Object>) ((Map<String, Object>) ((Map<String, Object>) ok.get("content"))
                    .get("application/json")).get("schema")).get("$ref");
            JsonNode body = OM_04_ReadApiTest.ok(PATHS.get(p.getKey()));
            assertThat(schemas.validate(ref.replace("../", ""), body)).as(p.getKey() + " → " + body).isEmpty();
        }
        assertThat(PATHS.keySet()).allSatisfy(k -> assertThat(paths).containsKey(k));
    }
}
