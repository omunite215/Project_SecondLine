package com.secondline.ledger.security;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.JsonNode;
import com.nimbusds.jose.JOSEObjectType;
import com.nimbusds.jose.PlainHeader;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.PlainJWT;
import com.secondline.contracts.Contracts;
import com.secondline.contracts.SchemaRegistry;
import com.secondline.gateway.client.ServiceTokens;
import com.secondline.gateway.token.RunGrant;
import com.secondline.gateway.token.RunTokens;
import com.secondline.ledger.Bundles;
import com.secondline.ledger.LedgerAuth;
import com.secondline.ledger.LedgerDb;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.yaml.snakeyaml.Yaml;

/**
 * OM-07 §11 §8 REQ-016 REQ-005 SEC-02 F9 T-SEC-01: the ledger's three realms. /internal/** takes only the gateway
 * service JWT for the ns in the path; /admin/** only the operator credential (plus the gateway's register_run);
 * /review/** and anything unlisted nobody yet. An agent run token is refused everywhere and moves no state.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class T_SEC_01_LedgerRealmsTest {
    static final SchemaRegistry SCHEMAS = SchemaRegistry.load();
    static final Path OPENAPI = Path.of(System.getProperty("contracts.root"), "openapi");

    @DynamicPropertySource
    static void props(DynamicPropertyRegistry r) {
        LedgerDb.migrate();
        r.add("spring.datasource.url", LedgerDb::jdbcUrl);
        r.add("spring.datasource.username", () -> "ledger_svc");
        r.add("spring.datasource.password", () -> LedgerDb.APP_PW);
        LedgerAuth.register(r);
    }

    @Autowired
    TestRestTemplate http;

    UUID ns;
    UUID other;

    ResponseEntity<String> call(HttpMethod method, String path, String token, String body) {
        return http.exchange(path, method, new HttpEntity<>(body, LedgerAuth.bearer(token)), String.class);
    }

    JsonNode json(ResponseEntity<String> r) throws Exception {
        return Contracts.MAPPER.readTree(r.getBody());
    }

    void assertDenied(ResponseEntity<String> r, String what) throws Exception {
        assertThat(r.getStatusCode().value()).as(what).isEqualTo(403);
        JsonNode b = json(r);
        assertThat(b.get("error_code").asText()).as(what).isEqualTo("PERMISSION_DENIED");
        assertThat(SCHEMAS.validate("error_response.schema.json", b)).as(what).isEmpty();
    }

    UUID loadedNs() throws Exception {
        UUID id = UUID.fromString(json(call(HttpMethod.POST, "/admin/v1/ns", LedgerAuth.OPERATOR, null)).get("ns").asText());
        assertThat(call(HttpMethod.POST, "/admin/v1/ns/" + id + ":load", LedgerAuth.OPERATOR, Bundles.minimal().toString())
                .getStatusCode().value()).isEqualTo(201);
        return id;
    }

    String stateHash(UUID id) throws Exception {
        return json(call(HttpMethod.GET, "/admin/v1/ns/" + id + "/state-hash", LedgerAuth.OPERATOR, null)).get("state_hash").asText();
    }

    String runBody(UUID id) {
        return Contracts.MAPPER.createObjectNode().put("ns", id.toString()).put("controls", "full")
                .put("agent_id", "agt_00000001").put("manifest_ref", "experiments/manifests/pilot-001.json").toString();
    }

    /** Every route the two ledger OpenAPI contracts declare, path variables filled (ns = the given one). */
    @SuppressWarnings("unchecked")
    static List<Map.Entry<HttpMethod, String>> contractRoutes(UUID id) throws Exception {
        List<Map.Entry<HttpMethod, String>> out = new ArrayList<>();
        for (String file : List.of("ledger-internal.yaml", "ledger-admin.yaml")) {
            Map<String, Object> doc = new Yaml().load(Files.readString(OPENAPI.resolve(file)));
            for (var p : ((Map<String, Map<String, Object>>) doc.get("paths")).entrySet()) {
                String path = p.getKey().replace("{ns}", id.toString()).replaceAll("\\{[a-zA-Z_]+}", "xyz_00000001");
                for (String m : p.getValue().keySet()) out.add(Map.entry(HttpMethod.valueOf(m.toUpperCase()), path));
            }
        }
        assertThat(out).hasSizeGreaterThan(15); // the parse found the routes, not an empty map
        return out;
    }

    @BeforeEach
    void namespaces() throws Exception {
        ns = loadedNs();
        other = loadedNs();
    }

    @Test
    void T_SEC_01_agentRunTokenRejectedOnEveryLedgerRoute() throws Exception {
        UUID run = UUID.fromString(json(call(HttpMethod.POST, "/admin/v1/runs", LedgerAuth.OPERATOR, runBody(ns))).get("run_id").asText());
        RunTokens runTokens = new RunTokens(LedgerAuth.RUN, Clock.systemUTC(), Duration.ofMinutes(30));
        String agent = runTokens.issue(new RunGrant(run, ns, Bundles.minimal().get("scenario_id").asText(), "agt_00000001",
                "full", List.of("get_break", "propose_adjustment"))).token();
        // Key confusion: even a run token signed with the service key is not a service token.
        String confused = new RunTokens(LedgerAuth.SERVICE, Clock.systemUTC(), Duration.ofMinutes(30)).issue(new RunGrant(run, ns,
                Bundles.minimal().get("scenario_id").asText(), "agt_00000001", "full", List.of("get_break"))).token();
        String before = stateHash(ns);
        String action = Files.readString(Path.of(System.getProperty("contracts.root"), "examples/actions/proposed_action_adjustment.json"));
        for (var route : contractRoutes(ns)) {
            String body = route.getKey() == HttpMethod.GET || route.getKey() == HttpMethod.DELETE ? null
                    : route.getValue().endsWith(":load") ? Bundles.minimal().toString()
                    : route.getValue().endsWith("/runs") ? runBody(ns) : action;
            for (String token : new String[] {agent, confused, null, "not-a-jwt"}) {
                assertDenied(call(route.getKey(), route.getValue(), token, body), route + " with " + (token == null ? "no token" : token.substring(0, 6)));
            }
        }
        assertThat(stateHash(ns)).isEqualTo(before);
        assertThat(LedgerDb.query(LedgerDb.app(), "SELECT status FROM ledger.namespaces WHERE ns = ?", ns)).isEqualTo("LOADED");
    }

    @Test
    void T_SEC_01_serviceTokenIsBoundToItsNamespace() throws Exception {
        assertThat(call(HttpMethod.GET, "/internal/v1/ns/" + ns + "/breaks", LedgerAuth.service(ns), null).getStatusCode().value())
                .isEqualTo(200);
        assertDenied(call(HttpMethod.GET, "/internal/v1/ns/" + other + "/breaks", LedgerAuth.service(ns), null), "cross-ns read");
        String decision = Files.readString(Path.of(System.getProperty("contracts.root"), "examples/runs/decision_log_entry_policy_deny.json"));
        long rows = Long.parseLong(LedgerDb.query(LedgerDb.app(), "SELECT count(*) FROM ledger.policy_decisions WHERE ns = ?", other));
        assertDenied(call(HttpMethod.POST, "/internal/v1/ns/" + other + "/decisions", LedgerAuth.service(ns), decision), "cross-ns write");
        assertThat(LedgerDb.query(LedgerDb.app(), "SELECT count(*) FROM ledger.policy_decisions WHERE ns = ?", other))
                .isEqualTo(Long.toString(rows));
        // Path tricks don't move the token into another ns: the ns segment is compared as a whole, decoded.
        assertDenied(call(HttpMethod.GET, "/internal/v1/ns/" + other + "/../" + ns + "/breaks", LedgerAuth.service(ns), null), "dot segments");
        assertDenied(call(HttpMethod.GET, "/internal/v1/ns/" + ns.toString().toUpperCase() + "x/breaks", LedgerAuth.service(ns), null), "suffix");
    }

    @Test
    void T_SEC_01_serviceTokenOnlyRegistersRunsForItsNamespace() throws Exception {
        assertDenied(call(HttpMethod.POST, "/admin/v1/ns", LedgerAuth.service(ns), null), "create ns");
        assertDenied(call(HttpMethod.GET, "/admin/v1/ns/" + ns + "/state-hash", LedgerAuth.service(ns), null), "state hash");
        assertDenied(call(HttpMethod.DELETE, "/admin/v1/ns/" + ns, LedgerAuth.service(ns), null), "retire");
        assertDenied(call(HttpMethod.POST, "/admin/v1/runs", LedgerAuth.service(ns), runBody(other)), "run for another ns");
        assertThat(call(HttpMethod.POST, "/admin/v1/runs", LedgerAuth.service(ns), runBody(ns)).getStatusCode().value()).isEqualTo(201);
    }

    @Test
    void T_SEC_01_operatorCredentialStaysInTheAdminRealm() throws Exception {
        assertDenied(call(HttpMethod.GET, "/internal/v1/ns/" + ns + "/breaks", LedgerAuth.OPERATOR, null), "operator on internal");
        assertDenied(call(HttpMethod.GET, "/admin/v1/ns/" + ns + "/state-hash", LedgerAuth.OPERATOR + "x", null), "operator + suffix");
        assertDenied(call(HttpMethod.GET, "/admin/v1/ns/" + ns + "/state-hash", LedgerAuth.OPERATOR.substring(1), null), "operator prefix cut");
        HttpHeaders basic = new HttpHeaders();
        basic.setBasicAuth("operator", LedgerAuth.OPERATOR);
        ResponseEntity<String> r = http.exchange("/admin/v1/ns/" + ns + "/state-hash", HttpMethod.GET, new HttpEntity<>(basic), String.class);
        assertDenied(r, "basic auth");
    }

    @Test
    void T_SEC_01_forgedServiceTokensAreRejected() throws Exception {
        String path = "/internal/v1/ns/" + ns + "/breaks";
        Instant past = Instant.now().minusSeconds(600);
        Map<String, String> forged = Map.of(
                "run-token key", LedgerAuth.forge(LedgerAuth.RUN, ServiceTokens.TYPE, ns, c -> c),
                "run token type", LedgerAuth.forge(LedgerAuth.SERVICE, RunTokens.TYPE, ns, c -> c),
                "no type", LedgerAuth.forge(LedgerAuth.SERVICE, null, ns, c -> c),
                "audience", LedgerAuth.forge(LedgerAuth.SERVICE, ServiceTokens.TYPE, ns, c -> c.audience(List.of("ledger", "opa"))),
                "issuer", LedgerAuth.forge(LedgerAuth.SERVICE, ServiceTokens.TYPE, ns, c -> c.issuer("someone-else")),
                "expired", LedgerAuth.forge(LedgerAuth.SERVICE, ServiceTokens.TYPE, ns, c -> c.issueTime(Date.from(past))
                        .notBeforeTime(Date.from(past)).expirationTime(Date.from(past.plusSeconds(60)))),
                "not yet valid", LedgerAuth.forge(LedgerAuth.SERVICE, ServiceTokens.TYPE, ns, c -> c.notBeforeTime(Date.from(Instant.now().plusSeconds(600)))),
                "long-lived", LedgerAuth.forge(LedgerAuth.SERVICE, ServiceTokens.TYPE, ns, c -> c.expirationTime(Date.from(Instant.now().plusSeconds(86_400)))),
                "no ns", LedgerAuth.forge(LedgerAuth.SERVICE, ServiceTokens.TYPE, ns, c -> c.claim("ns", null)),
                "unsigned", new PlainJWT(new PlainHeader.Builder().type(ServiceTokens.TYPE).build(), new JWTClaimsSet.Builder()
                        .issuer("secondline-gateway").subject("gateway").audience("ledger").claim("ns", ns.toString())
                        .expirationTime(Date.from(Instant.now().plusSeconds(60))).build()).serialize());
        for (var f : forged.entrySet()) assertDenied(call(HttpMethod.GET, path, f.getValue(), null), f.getKey());
        String good = LedgerAuth.service(ns);
        String[] parts = good.split("\\.");
        String tampered = parts[0] + "." + parts[1].substring(0, parts[1].length() - 2) + "AA." + parts[2];
        assertDenied(call(HttpMethod.GET, path, tampered, null), "tampered payload");
    }

    @Test
    void T_SEC_01_authenticatedUnknownRouteIsAPlain404() {
        // Inside a realm, an unknown route is still ErrorAdvice's bodiless 404, not a 403 from the /error dispatch.
        ResponseEntity<String> r = call(HttpMethod.GET, "/internal/v1/ns/" + ns + "/nothing-here", LedgerAuth.service(ns), null);
        assertThat(r.getStatusCode().value()).isEqualTo(404);
        assertThat(r.getBody()).isNull();
    }

    @Test
    void T_SEC_01_unlistedRealmsAreClosedHealthIsOpen() throws Exception {
        assertDenied(call(HttpMethod.GET, "/review/v1/approvals", LedgerAuth.OPERATOR, null), "review realm before OM-20");
        assertDenied(call(HttpMethod.GET, "/v1/anything", LedgerAuth.service(ns), null), "unlisted path");
        assertThat(call(HttpMethod.GET, "/actuator/health/readiness", null, null).getStatusCode().value()).isEqualTo(200);
    }
}
