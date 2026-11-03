package com.secondline.gateway.observe;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

import com.secondline.contracts.Contracts;
import com.secondline.gateway.TestKeys;
import com.secondline.gateway.pipeline.ToolPipeline;
import com.secondline.gateway.pipeline.ToolResult;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import io.micrometer.core.instrument.distribution.CountAtBucket;
import io.opentelemetry.sdk.testing.exporter.InMemorySpanExporter;
import io.opentelemetry.sdk.trace.data.SpanData;
import java.time.Duration;
import java.util.Arrays;
import java.util.List;
import java.util.UUID;
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
import org.springframework.test.context.bean.override.mockito.MockitoBean;

/** OM-05 G13 MET-09 NFR-08: gateway.onpath histogram + spans with run_id/action_id, never a token. */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties = "management.tracing.sampling.probability=1.0")
class OM_05_ObservabilityTest {
    static final UUID RUN = UUID.fromString("22222222-2222-4222-8222-222222222222");
    static final String ACTION = "7d1e2a9c-0b3f-4c5d-9e8f-1a2b3c4d5e6f";
    static final InMemorySpanExporter SPANS = InMemorySpanExporter.create();

    @TestConfiguration
    static class Exporter {
        @Bean
        InMemorySpanExporter inMemorySpanExporter() {
            return SPANS;
        }
    }

    @DynamicPropertySource
    static void config(DynamicPropertyRegistry r) {
        r.add("gateway.signing-jwk-path", TestKeys::path);
        r.add("gateway.ledger-url", () -> "http://127.0.0.1:1");
        r.add("gateway.opa-url", () -> "http://127.0.0.1:1");
    }

    @Autowired
    TestRestTemplate http;

    @Autowired
    MeterRegistry meters;

    @MockitoBean
    ToolPipeline pipeline;

    void call(String tool, String body) {
        HttpHeaders h = new HttpHeaders();
        h.setContentType(MediaType.APPLICATION_JSON);
        h.set("Authorization", "Bearer secret.token.value");
        http.postForEntity("/v1/runs/" + RUN + "/tools/" + tool, new HttpEntity<>(body, h), String.class);
    }

    @Test
    void OM_05_onPathTimerRecordsEveryToolCallWithSloBuckets() throws Exception {
        when(pipeline.handle(any())).thenReturn(new ToolResult(200, Contracts.MAPPER.readTree("{}")));
        call("get_break", "{\"run_id\":\"" + RUN + "\"}");
        Timer t = meters.find("gateway.onpath").tag("tool", "get_break").tag("status", "200").timer();
        assertThat(t).isNotNull();
        assertThat(t.count()).isGreaterThanOrEqualTo(1);
        List<Double> buckets = Arrays.stream(t.takeSnapshot().histogramCounts()).map(CountAtBucket::bucket)
                .map(ns -> ns / 1_000_000.0).toList();
        assertThat(buckets).contains(1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0);
    }

    @Test
    void OM_05_unknownToolNamesDoNotExplodeMetricCardinality() throws Exception {
        when(pipeline.handle(any())).thenReturn(new ToolResult(403, Contracts.MAPPER.readTree("{}")));
        call("random_" + UUID.randomUUID().toString().substring(0, 8), "{}");
        assertThat(meters.find("gateway.onpath").tag("tool", "unknown").timer()).isNotNull();
    }

    @Test
    void OM_05_spanCarriesRunAndActionIdButNoToken() throws Exception {
        SPANS.reset();
        when(pipeline.handle(any())).thenReturn(new ToolResult(200, Contracts.MAPPER.readTree("{}")));
        call("propose_adjustment", "{\"run_id\":\"" + RUN + "\",\"action_id\":\"" + ACTION + "\"}");
        long deadline = System.nanoTime() + Duration.ofSeconds(12).toNanos(); // BatchSpanProcessor flushes every 5 s
        List<SpanData> spans = SPANS.getFinishedSpanItems();
        while (spans.stream().noneMatch(s -> s.getAttributes().asMap().toString().contains(ACTION)) && System.nanoTime() < deadline) {
            Thread.sleep(50);
            spans = SPANS.getFinishedSpanItems();
        }
        SpanData tool = spans.stream().filter(s -> s.getAttributes().asMap().toString().contains(ACTION)).findFirst().orElseThrow();
        String attrs = tool.getAttributes().asMap().toString();
        assertThat(attrs).contains("run_id").contains(RUN.toString()).contains("action_id");
        assertThat(spans.toString()).doesNotContain("secret.token.value");
    }
}
