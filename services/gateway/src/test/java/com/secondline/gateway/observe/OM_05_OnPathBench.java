package com.secondline.gateway.observe;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.node.ObjectNode;
import com.secondline.contracts.CanonicalJson;
import com.secondline.contracts.Contracts;
import com.secondline.gateway.TestKeys;
import com.secondline.gateway.route.ToolRoute;
import com.secondline.gateway.route.ToolRoutes;
import com.secondline.gateway.token.RunGrant;
import com.secondline.gateway.token.RunTokens;
import com.sun.net.httpserver.HttpServer;
import io.micrometer.core.instrument.Meter;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import io.micrometer.core.instrument.config.MeterFilter;
import io.micrometer.core.instrument.distribution.DistributionStatisticConfig;
import io.micrometer.core.instrument.distribution.ValueAtPercentile;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.UUID;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.context.annotation.Bean;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

/**
 * OM-05 G13 (card: "on-path p50/p95/p99 logged locally (measured, not claimed)"). 2,000 tool calls (1,000 reads,
 * 1,000 OPA-checked writes, controls=full) through the real HTTP stack, filter, pipeline and clients, against a stub
 * ledger and stub OPA on localhost. Writes build/reports/om05-onpath.json, labelled SIMULATED: these numbers say
 * nothing about a real ledger, OPA or network, and are not an H2 result.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class OM_05_OnPathBench {
    static final int CALLS = 2000;
    static final UUID RUN = UUID.fromString("3f2e1d0c-4b5a-4968-8776-655443322110");
    static final UUID NS = UUID.fromString("11111111-1111-4111-8111-111111111111");
    static final HttpServer STUBS = stubs();

    static HttpServer stubs() {
        // The test JVM sets sun.net.httpserver.nodelay=true (build.gradle.kts): without it the JDK HttpServer adds ~40 ms
        // per round trip (45 ms vs 3 ms measured), and the bench would measure the stub instead of the gateway.
        if (!"true".equals(System.getProperty("sun.net.httpserver.nodelay"))) {
            throw new IllegalStateException("run with -Dsun.net.httpserver.nodelay=true (set in services/gateway/build.gradle.kts)");
        }
        try {
            Path ex = Path.of(System.getProperty("contracts.root"), "examples/tools");
            String breakOut = strip(Files.readString(ex.resolve("get_break.output.json")));
            String receipt = strip(Files.readString(ex.resolve("propose_adjustment.output.json")));
            String allow = "{\"result\":{\"decision\":\"ALLOW\",\"reason\":\"\",\"bundle_hash\":\"sha256:" + "a".repeat(64) + "\"}}";
            HttpServer s = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
            s.setExecutor(java.util.concurrent.Executors.newFixedThreadPool(4));
            s.createContext("/", x -> {
                x.getRequestBody().readAllBytes();
                String p = x.getRequestURI().getPath();
                String body = p.startsWith("/v1/data/") ? allow : p.endsWith("/decisions") ? "{}" : p.endsWith("/actions") ? receipt : breakOut;
                byte[] out = body.getBytes(StandardCharsets.UTF_8);
                x.sendResponseHeaders(p.endsWith("/decisions") ? 201 : 200, out.length);
                x.getResponseBody().write(out);
                x.close();
            });
            s.start();
            return s;
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    static String strip(String json) {
        ObjectNode o = (ObjectNode) CanonicalJson.parse(json);
        o.remove("x-validates");
        return o.toString();
    }

    @AfterAll
    static void stop() {
        STUBS.stop(0);
    }

    @DynamicPropertySource
    static void config(DynamicPropertyRegistry r) {
        String url = "http://127.0.0.1:" + STUBS.getAddress().getPort();
        r.add("gateway.signing-jwk-path", TestKeys::path);
        r.add("gateway.ledger-url", () -> url);
        r.add("gateway.opa-url", () -> url);
        r.add("gateway.budget.max-calls", () -> "100000");
    }

    /** Client-side percentiles for the bench only; the production timer exports its SLO histogram. */
    @TestConfiguration
    static class Percentiles {
        @Bean
        MeterFilter onPathPercentiles() {
            return new MeterFilter() {
                @Override
                public DistributionStatisticConfig configure(Meter.Id id, DistributionStatisticConfig config) {
                    if (!id.getName().equals("gateway.onpath")) return config;
                    return DistributionStatisticConfig.builder().percentiles(0.5, 0.95, 0.99).build().merge(config);
                }
            };
        }
    }

    @Autowired
    TestRestTemplate http;

    @Autowired
    RunTokens tokens;

    @Autowired
    MeterRegistry meters;

    @Test
    void OM_05_onPathPercentilesAreMeasuredAndReported() throws Exception {
        String token = tokens.issue(new RunGrant(RUN, NS, "scn_0000A001", "agt_00000001", "full",
                ToolRoutes.all().stream().map(ToolRoute::tool).sorted().toList())).token();
        HttpHeaders h = new HttpHeaders();
        h.setContentType(MediaType.APPLICATION_JSON);
        h.setBearerAuth(token);
        String read = "{\"run_id\":\"" + RUN + "\",\"break_id\":\"brk_0000AB12\"}";
        ObjectNode write = (ObjectNode) CanonicalJson.parse(Files.readString(
                Path.of(System.getProperty("contracts.root"), "examples/actions/proposed_action_adjustment.json")));
        write.remove("x-validates");
        for (int i = 0; i < CALLS; i++) {
            boolean isRead = i % 2 == 0;
            var r = http.postForEntity("/v1/runs/" + RUN + "/tools/" + (isRead ? "get_break" : "propose_adjustment"),
                    new HttpEntity<>(isRead ? read : write.toString(), h), String.class);
            assertThat(r.getStatusCode().value()).as(r.getBody()).isEqualTo(200);
        }
        ObjectNode report = Contracts.MAPPER.createObjectNode()
                .put("label", "SIMULATED (stub ledger + stub OPA on localhost, in-process; not an H2 result)")
                .put("metric", "gateway.onpath (request received -> response sent)")
                .put("controls", "full").put("calls", CALLS).put("measured_at", Instant.now().toString())
                .put("jvm", System.getProperty("java.version")).put("cpus", Runtime.getRuntime().availableProcessors())
                .put("note", "each call makes 2 (read) or 3 (write: OPA, ledger, decision log) localhost HTTP hops to stubs");
        for (String tool : new String[] {"get_break", "propose_adjustment"}) {
            Timer t = meters.find("gateway.onpath").tag("tool", tool).tag("status", "200").timer();
            assertThat(t).as(tool).isNotNull();
            assertThat(t.count()).isEqualTo(CALLS / 2);
            ObjectNode o = report.putObject(tool).put("n", t.count());
            for (ValueAtPercentile v : t.takeSnapshot().percentileValues()) {
                o.put("p" + Math.round(v.percentile() * 100) + "_ms", Math.round(v.value(TimeUnit.MICROSECONDS)) / 1000.0);
            }
            assertThat(o.has("p50_ms") && o.has("p95_ms") && o.has("p99_ms")).isTrue();
        }
        Path out = Path.of("build/reports/om05-onpath.json");
        Files.createDirectories(out.getParent());
        Files.writeString(out, Contracts.MAPPER.writerWithDefaultPrettyPrinter().writeValueAsString(report) + "\n");
        System.out.println("OM-05 on-path: " + report);
    }
}
