package com.secondline.ledger.e2e;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.secondline.contracts.CanonicalJson;
import com.secondline.contracts.Contracts;
import com.secondline.contracts.SchemaRegistry;
import com.secondline.gateway.client.DecisionLog;
import com.secondline.gateway.client.LedgerClient;
import com.secondline.gateway.client.PolicyClient;
import com.secondline.gateway.client.ServiceTokens;
import com.secondline.gateway.guard.InMemoryRunGuard;
import com.secondline.gateway.pipeline.ToolCall;
import com.secondline.gateway.pipeline.ToolPipeline;
import com.secondline.gateway.pipeline.ToolResult;
import com.secondline.gateway.route.ToolRoute;
import com.secondline.gateway.route.ToolRoutes;
import com.secondline.gateway.schema.InputSchemas;
import com.secondline.gateway.token.RunGrant;
import com.secondline.gateway.token.RunTokens;
import com.secondline.gateway.token.SigningKeys;
import com.secondline.ledger.Bundles;
import com.secondline.ledger.LedgerDb;
import com.sun.net.httpserver.HttpServer;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Clock;
import java.time.Duration;
import java.util.UUID;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

/**
 * OM-05 Task 6 (Review Focus 4, card done criterion): the real gateway pipeline against the real ledger on
 * Testcontainers, with only OPA stubbed. A call OPA denies leaves the ledger state hash unchanged and is recorded in
 * the ledger's policy_decisions; an allowed read goes all the way through.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class OM_05_GatewayAgainstLedgerTest {
    static HttpServer opa;

    @DynamicPropertySource
    static void db(DynamicPropertyRegistry r) {
        LedgerDb.migrate();
        r.add("spring.datasource.url", LedgerDb::jdbcUrl);
        r.add("spring.datasource.username", () -> "ledger_svc");
        r.add("spring.datasource.password", () -> LedgerDb.APP_PW);
    }

    @BeforeAll
    static void opaDeniesWrites() throws Exception {
        opa = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        opa.createContext("/v1/data/secondline/decision", ex -> {
            byte[] out = ("{\"result\":{\"decision\":\"DENY\",\"reason\":\"posts to suspense\",\"bundle_hash\":\"sha256:"
                    + "a".repeat(64) + "\"}}").getBytes(StandardCharsets.UTF_8);
            ex.getRequestBody().readAllBytes();
            ex.sendResponseHeaders(200, out.length);
            ex.getResponseBody().write(out);
            ex.close();
        });
        opa.start();
    }

    @AfterAll
    static void stop() {
        opa.stop(0);
    }

    @LocalServerPort
    int port;

    @Autowired
    TestRestTemplate http;

    JsonNode post(String path, String json) throws Exception {
        HttpHeaders h = new HttpHeaders();
        h.setContentType(MediaType.APPLICATION_JSON);
        return Contracts.MAPPER.readTree(http.postForEntity(path, new HttpEntity<>(json, h), String.class).getBody());
    }

    String stateHash(UUID ns) throws Exception {
        return Contracts.MAPPER.readTree(http.getForEntity("/admin/v1/ns/" + ns + "/state-hash", String.class).getBody())
                .get("state_hash").asText();
    }

    @Test
    void OM_05_deniedCallLeavesStateHash() throws Exception {
        UUID ns = UUID.fromString(post("/admin/v1/ns", "").get("ns").asText());
        post("/admin/v1/ns/" + ns + ":load", Bundles.minimal().toString());
        UUID run = UUID.fromString(post("/admin/v1/runs", Contracts.MAPPER.createObjectNode().put("ns", ns.toString())
                .put("controls", "full").put("agent_id", "agt_00000001")
                .put("manifest_ref", "experiments/manifests/pilot-001.json").toString()).get("run_id").asText());

        SigningKeys keys = SigningKeys.generate("gw-e2e000000000001");
        RunTokens tokens = new RunTokens(keys, Clock.systemUTC(), Duration.ofMinutes(30));
        LedgerClient ledger = new LedgerClient("http://127.0.0.1:" + port, new ServiceTokens(keys, Clock.systemUTC()), Duration.ofSeconds(5));
        ToolPipeline pipeline = new ToolPipeline(tokens, new InputSchemas(SchemaRegistry.load()), new InMemoryRunGuard(100),
                new PolicyClient("http://127.0.0.1:" + opa.getAddress().getPort(), Duration.ofMillis(500)), ledger,
                new DecisionLog(ledger, SchemaRegistry.load()), Clock.systemUTC(), new SimpleMeterRegistry());
        String token = tokens.issue(new RunGrant(run, ns, Bundles.minimal().get("scenario_id").asText(), "agt_00000001", "full",
                ToolRoutes.all().stream().map(ToolRoute::tool).sorted().toList())).token();

        // 1. A write OPA denies: nothing changes, the deny is on record in the ledger.
        String before = stateHash(ns);
        ObjectNode action = (ObjectNode) CanonicalJson.parse(Files.readString(
                Path.of(System.getProperty("contracts.root"), "examples/actions/proposed_action_adjustment.json")));
        action.remove("x-validates");
        action.put("run_id", run.toString());
        ToolResult denied = pipeline.handle(new ToolCall(token, run, "propose_adjustment", action, UUID.randomUUID()));
        assertThat(denied.status()).isEqualTo(403);
        assertThat(denied.body().get("error_code").asText()).isEqualTo("POLICY_DENIED");
        assertThat(stateHash(ns)).isEqualTo(before);
        assertThat(LedgerDb.query(LedgerDb.app(), "SELECT decision || '/' || stage || '/' || policy_bundle_hash"
                + " FROM ledger.policy_decisions WHERE ns = ? AND run_id = ?", ns, run))
                .isEqualTo("DENY/policy/sha256:" + "a".repeat(64));

        // 2. An allowed read goes gateway → real ledger → contract-valid answer, logged ALLOW routed.
        ObjectNode q = Contracts.MAPPER.createObjectNode().put("run_id", run.toString()).put("break_id", "brk_0000F001");
        ToolResult read = pipeline.handle(new ToolCall(token, run, "get_break", q, UUID.randomUUID()));
        assertThat(read.status()).isEqualTo(200);
        assertThat(SchemaRegistry.load().validate("tools/get_break.output.schema.json", read.body())).isEmpty();
        assertThat(LedgerDb.query(LedgerDb.app(), "SELECT count(*) FROM ledger.policy_decisions WHERE ns = ? AND run_id = ?"
                + " AND decision = 'ALLOW' AND stage = 'routed' AND tool = 'get_break'", ns, run)).isEqualTo("1");
        assertThat(stateHash(ns)).isEqualTo(before); // reads don't move state either
    }
}
