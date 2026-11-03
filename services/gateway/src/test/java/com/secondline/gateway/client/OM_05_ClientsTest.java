package com.secondline.gateway.client;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.nimbusds.jose.crypto.Ed25519Verifier;
import com.nimbusds.jwt.SignedJWT;
import com.secondline.contracts.CanonicalJson;
import com.secondline.contracts.Contracts;
import com.secondline.contracts.SchemaRegistry;
import com.secondline.contracts.generated.ErrorCode;
import com.secondline.gateway.GatewayException;
import com.secondline.gateway.guard.InMemoryRunGuard;
import com.secondline.gateway.route.RouteKind;
import com.secondline.gateway.route.ToolRoute;
import com.secondline.gateway.route.ToolRoutes;
import com.secondline.gateway.schema.InputSchemas;
import com.secondline.gateway.token.SigningKeys;
import java.io.FileInputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.UUID;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.yaml.snakeyaml.Yaml;

/** OM-05 Task 3 §7 §10 §11 G9 G10 G11 G12: the gateway's outbound calls, each failing closed. */
class OM_05_ClientsTest {
    static final Path CONTRACTS = Path.of(System.getProperty("contracts.root"));
    static final UUID NS = UUID.fromString("11111111-1111-4111-8111-111111111111");
    static final UUID RUN = UUID.fromString("22222222-2222-4222-8222-222222222222");
    static final Instant NOW = Instant.parse("2026-11-03T12:00:00Z");
    static final String ERROR_BODY =
            "{\"error_code\":\"STATE_CONFLICT\",\"message\":\"expected_state_version 7, current 8\",\"request_id\":\"0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d\"}";

    final SigningKeys keys = SigningKeys.generate("gw-test-v1");
    StubServer ledger;
    StubServer opa;
    LedgerClient ledgerClient;
    PolicyClient policy;

    @BeforeEach
    void up() throws Exception {
        ledger = new StubServer();
        opa = new StubServer();
        ServiceTokens svc = new ServiceTokens(keys, Clock.fixed(NOW, ZoneOffset.UTC));
        ledgerClient = new LedgerClient(ledger.url(), svc, Duration.ofMillis(500));
        policy = new PolicyClient(opa.url(), Duration.ofMillis(200));
    }

    @AfterEach
    void down() {
        ledger.close();
        opa.close();
    }

    static void code(ErrorCode expected, Runnable r) {
        assertThatThrownBy(r::run).isInstanceOf(GatewayException.class)
                .extracting(e -> ((GatewayException) e).code()).isEqualTo(expected);
    }

    // ---- routing ---------------------------------------------------------------------------------

    @Test
    @SuppressWarnings("unchecked")
    void OM_05_readRoutesMatchLedgerInternalYaml() throws Exception {
        Map<String, Object> doc;
        try (var in = new FileInputStream(CONTRACTS.resolve("openapi/ledger-internal.yaml").toFile())) {
            doc = new Yaml().load(in);
        }
        Map<String, String> expectedPath = new TreeMap<>();
        Map<String, List<String>> expectedQuery = new TreeMap<>();
        ((Map<String, Map<String, Object>>) doc.get("paths")).forEach((path, ops) -> {
            Object get = ops.get("get");
            if (!(get instanceof Map<?, ?> op) || op.get("operationId") == null) return;
            String tool = (String) op.get("operationId");
            List<String> q = new ArrayList<>();
            Object params = op.get("parameters");
            for (Object p : params == null ? List.of() : (List<Object>) params) {
                Map<String, Object> pm = (Map<String, Object>) p;
                if ("query".equals(pm.get("in"))) q.add((String) pm.get("name"));
            }
            expectedPath.put(tool, path);
            expectedQuery.put(tool, q);
        });
        Map<String, String> actualPath = new TreeMap<>();
        Map<String, List<String>> actualQuery = new TreeMap<>();
        for (ToolRoute r : ToolRoutes.all()) {
            if (r.kind() != RouteKind.READ) continue;
            actualPath.put(r.tool(), r.pathTemplate());
            actualQuery.put(r.tool(), r.queryParams());
        }
        assertThat(actualPath).isEqualTo(expectedPath);
        assertThat(actualQuery).isEqualTo(expectedQuery);
    }

    @Test
    void OM_05_everyToolHasARouteKind() throws Exception {
        JsonNode index = CanonicalJson.parse(Files.readString(CONTRACTS.resolve("tools/INDEX.json"))).path("tools");
        List<String> tools = new ArrayList<>();
        index.fieldNames().forEachRemaining(tools::add);
        assertThat(ToolRoutes.all().stream().map(ToolRoute::tool).sorted().toList()).isEqualTo(tools.stream().sorted().toList());
        for (String t : tools) {
            ToolRoute r = ToolRoutes.of(t);
            assertThat(r.risk()).as(t).isEqualTo(index.path(t).path("risk").asText());
            if (r.risk().equals("read")) assertThat(r.kind()).as(t).isIn(RouteKind.READ, RouteKind.UNROUTED);
            else assertThat(r.kind()).as(t).isIn(RouteKind.ACTION, RouteKind.SIMULATED);
        }
        assertThat(ToolRoutes.of("request_counterparty_clarification").kind()).isEqualTo(RouteKind.SIMULATED);
        assertThat(ToolRoutes.of("get_action_status").kind()).isEqualTo(RouteKind.UNROUTED);
        assertThat(ToolRoutes.of("get_approval_status").kind()).isEqualTo(RouteKind.UNROUTED);
        code(ErrorCode.PERMISSION_DENIED, () -> ToolRoutes.of("drop_tables"));
    }

    @Test
    void OM_05_readToolSendsPathAndQueryAndNeverTheRunId() throws Exception {
        ledger.reply = new StubServer.Reply(200, "{\"ok\":true}", 0);
        ObjectNode in = Contracts.MAPPER.createObjectNode().put("run_id", RUN.toString())
                .put("trade_id", "trd_00004521").put("as_of_version", 3);
        LedgerResponse r = ledgerClient.read(NS, ToolRoutes.of("read_trade"), in);
        assertThat(r.status()).isEqualTo(200);
        StubServer.Seen s = ledger.seen.get(0);
        assertThat(s.method()).isEqualTo("GET");
        assertThat(s.path()).isEqualTo("/internal/v1/ns/" + NS + "/trades/trd_00004521");
        assertThat(s.query()).isEqualTo("as_of_version=3");
        // optional query params that are absent are simply left out
        ledgerClient.read(NS, ToolRoutes.of("read_positions"), Contracts.MAPPER.createObjectNode().put("run_id", RUN.toString()));
        assertThat(ledger.seen.get(1).query()).isNull();
        assertThat(ledger.seen.get(1).path()).isEqualTo("/internal/v1/ns/" + NS + "/positions");
    }

    @Test
    void OM_05_readWithMissingPathParamFailsClosedWithoutCalling() {
        ObjectNode in = Contracts.MAPPER.createObjectNode().put("run_id", RUN.toString());
        code(ErrorCode.DOMAIN_INVALID, () -> ledgerClient.read(NS, ToolRoutes.of("get_break"), in));
        code(ErrorCode.RETRYABLE_UNAVAILABLE, () -> ledgerClient.read(NS, ToolRoutes.of("get_action_status"), in));
        assertThat(ledger.seen).isEmpty();
    }

    // ---- ledger writes, errors, availability ------------------------------------------------------

    @Test
    void OM_05_writePostsBodyUnchangedWithServiceJwt() throws Exception {
        ledger.reply = new StubServer.Reply(200, "{\"receipt\":1}", 0);
        JsonNode action = CanonicalJson.parse(Files.readString(CONTRACTS.resolve("examples/actions/proposed_action_adjustment.json")));
        ((ObjectNode) action).remove("x-validates");
        ledgerClient.postAction(NS, action);
        StubServer.Seen s = ledger.seen.get(0);
        assertThat(s.method()).isEqualTo("POST");
        assertThat(s.path()).isEqualTo("/internal/v1/ns/" + NS + "/actions");
        assertThat(CanonicalJson.canonicalize(s.body())).isEqualTo(CanonicalJson.canonicalize(action));
        String auth = s.headers().get("Authorization").get(0);
        assertThat(auth).startsWith("Bearer ");
        SignedJWT jwt = SignedJWT.parse(auth.substring(7));
        assertThat(jwt.verify(new Ed25519Verifier(keys.publicJwk()))).isTrue();
        assertThat(jwt.getHeader().getKeyID()).isEqualTo("gw-test-v1");
        assertThat(jwt.getHeader().getType().getType()).isEqualTo("sl-svc+jwt"); // never mistaken for a run token
        assertThat(jwt.getJWTClaimsSet().getAudience()).containsExactly("ledger");
        assertThat(jwt.getJWTClaimsSet().getSubject()).isEqualTo("gateway");
        assertThat(jwt.getJWTClaimsSet().getExpirationTime().toInstant()).isEqualTo(NOW.plusSeconds(60));
    }

    @Test
    void OM_05_ledgerContractErrorBodyPassesThrough() {
        ledger.reply = new StubServer.Reply(409, ERROR_BODY, 0);
        LedgerResponse r = ledgerClient.postAction(NS, Contracts.MAPPER.createObjectNode());
        assertThat(r.status()).isEqualTo(409);
        assertThat(CanonicalJson.canonicalize(r.body())).isEqualTo(CanonicalJson.canonicalize(ERROR_BODY));
    }

    @Test
    void OM_05_ledgerNonContractErrorBodyFailsClosed() {
        // e.g. a 404 page from a wrong path: never pass an invented outcome to the agent.
        ledger.reply = new StubServer.Reply(404, "<html>not found</html>", 0);
        code(ErrorCode.RETRYABLE_UNAVAILABLE, () -> ledgerClient.postAction(NS, Contracts.MAPPER.createObjectNode()));
        ledger.reply = new StubServer.Reply(400, "{\"error_code\":\"ORACLE_MISMATCH\",\"message\":\"x\",\"request_id\":\"0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d\"}", 0);
        code(ErrorCode.RETRYABLE_UNAVAILABLE, () -> ledgerClient.postAction(NS, Contracts.MAPPER.createObjectNode()));
    }

    @Test
    void OM_05_ledgerDownOr5xxOrSlowIsRetryableUnavailable() {
        ledger.reply = new StubServer.Reply(500, "{}", 0);
        code(ErrorCode.RETRYABLE_UNAVAILABLE, () -> ledgerClient.postAction(NS, Contracts.MAPPER.createObjectNode()));
        ledger.reply = new StubServer.Reply(200, "{}", 1500);
        code(ErrorCode.RETRYABLE_UNAVAILABLE, () -> ledgerClient.postAction(NS, Contracts.MAPPER.createObjectNode()));
        ledger.reply = new StubServer.Reply(200, "not json", 0);
        code(ErrorCode.RETRYABLE_UNAVAILABLE, () -> ledgerClient.postAction(NS, Contracts.MAPPER.createObjectNode()));
        ledger.reply = new StubServer.Reply(302, "{\"moved\":true}", 0); // a redirect is never an outcome
        code(ErrorCode.RETRYABLE_UNAVAILABLE, () -> ledgerClient.postAction(NS, Contracts.MAPPER.createObjectNode()));
        LedgerClient nowhere = new LedgerClient("http://127.0.0.1:1", new ServiceTokens(keys, Clock.systemUTC()), Duration.ofMillis(300));
        code(ErrorCode.RETRYABLE_UNAVAILABLE, () -> nowhere.postAction(NS, Contracts.MAPPER.createObjectNode()));
    }

    // ---- OPA ---------------------------------------------------------------------------------------

    @Test
    void OM_05_opaInputShapeAndAnswer() throws Exception {
        opa.reply = new StubServer.Reply(200, "{\"result\":{\"decision\":\"DENY\",\"reason\":\"posts to 1900\",\"bundle_hash\":\"sha256:"
                + "c".repeat(64) + "\"}}", 0);
        ObjectNode run = Contracts.MAPPER.createObjectNode().put("run_id", RUN.toString()).put("controls", "full");
        ObjectNode action = Contracts.MAPPER.createObjectNode().put("type", "ADJUSTMENT");
        PolicyDecision d = policy.decide(run, "propose_adjustment", action);
        assertThat(d.decision()).isEqualTo("DENY");
        assertThat(d.reason()).isEqualTo("posts to 1900");
        assertThat(d.bundleHash()).isEqualTo("sha256:" + "c".repeat(64));
        StubServer.Seen s = opa.seen.get(0);
        assertThat(s.method()).isEqualTo("POST");
        assertThat(s.path()).isEqualTo("/v1/data/secondline/decision");
        JsonNode sent = CanonicalJson.parse(s.body());
        assertThat(sent.path("input").path("tool").asText()).isEqualTo("propose_adjustment");
        assertThat(sent.path("input").path("run")).isEqualTo(run);
        assertThat(sent.path("input").path("action")).isEqualTo(action);
    }

    @Test
    void OM_05_opaTimeoutOrGarbageIsRetryableUnavailable() {
        ObjectNode empty = Contracts.MAPPER.createObjectNode();
        for (StubServer.Reply bad : List.of(
                new StubServer.Reply(200, "{\"result\":{\"decision\":\"ALLOW\",\"bundle_hash\":\"sha256:" + "c".repeat(64) + "\"}}", 400), // > 200 ms
                new StubServer.Reply(500, "{}", 0),
                new StubServer.Reply(200, "{}", 0),                                              // undefined decision
                new StubServer.Reply(200, "{\"result\":{\"decision\":\"MAYBE\"}}", 0),            // unknown value
                new StubServer.Reply(200, "{\"result\":{\"decision\":\"ALLOW\"}}", 0),            // no bundle hash
                new StubServer.Reply(200, "not json", 0))) {
            opa.reply = bad;
            code(ErrorCode.RETRYABLE_UNAVAILABLE, () -> policy.decide(empty, "propose_adjustment", empty));
        }
    }

    // ---- guard, schemas, decision log -------------------------------------------------------------

    @Test
    void OM_05_budgetExhaustionAndHaltAreRunHalted() {
        InMemoryRunGuard guard = new InMemoryRunGuard(2);
        guard.admit(RUN);
        guard.admit(RUN);
        code(ErrorCode.RUN_HALTED, () -> guard.admit(RUN)); // the call budget, every condition
        UUID other = UUID.randomUUID();
        guard.halt(other);
        assertThat(guard.halted(other)).isTrue(); // the pipeline applies halts only in monitor/full (ADR-014)
        assertThat(guard.halted(RUN)).isFalse();
        java.util.concurrent.atomic.AtomicInteger lookups = new java.util.concurrent.atomic.AtomicInteger();
        java.util.function.IntSupplier oneBreak = () -> { lookups.incrementAndGet(); return 1; };
        assertThat(guard.tryConsumeMessage(RUN, oneBreak)).isTrue();
        assertThat(guard.tryConsumeMessage(RUN, oneBreak)).isFalse(); // C_msg exhausted → POLICY_DENIED (ADR-014)
        assertThat(lookups.get()).isEqualTo(1); // the run's budget is looked up once
    }

    @Test
    void OM_05_schemaErrorsAreDomainInvalidAndNeverEchoInput() {
        InputSchemas schemas = new InputSchemas(SchemaRegistry.load());
        ObjectNode bad = Contracts.MAPPER.createObjectNode().put("run_id", "<script>alert(1)</script>").put("break_id", "SLCANARY-x");
        assertThatThrownBy(() -> schemas.validate("get_break", bad)).isInstanceOf(GatewayException.class)
                .satisfies(e -> {
                    GatewayException g = (GatewayException) e;
                    assertThat(g.code()).isEqualTo(ErrorCode.DOMAIN_INVALID);
                    assertThat(g.detail()).doesNotContain("script").doesNotContain("SLCANARY");
                });
        schemas.validate("get_break", Contracts.MAPPER.createObjectNode().put("run_id", RUN.toString()).put("break_id", "brk_0000AB12"));
        code(ErrorCode.PERMISSION_DENIED, () -> schemas.validate("drop_tables", bad));
    }

    @Test
    void OM_05_decisionLogValidatesBeforeSending() {
        ledger.reply = new StubServer.Reply(201, "{}", 0);
        DecisionLog log = new DecisionLog(ledgerClient, SchemaRegistry.load());
        DecisionLogEntry ok = new DecisionLogEntry(UUID.randomUUID(), RUN, "propose_adjustment", null, "DENY",
                "POLICY_DENIED", "full", null, "policy", NOW);
        log.record(NS, ok);
        assertThat(ledger.seen).hasSize(1);
        assertThat(ledger.seen.get(0).path()).isEqualTo("/internal/v1/ns/" + NS + "/decisions");
        DecisionLogEntry bad = new DecisionLogEntry(UUID.randomUUID(), RUN, "propose_adjustment", null, "DENY",
                "POLICY_DENIED", "full", null, "somewhere", NOW);
        code(ErrorCode.RETRYABLE_UNAVAILABLE, () -> log.record(NS, bad));
        assertThat(ledger.seen).hasSize(1);
    }
}
