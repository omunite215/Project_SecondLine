package com.secondline.gateway.web;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.JsonNode;
import com.secondline.contracts.CanonicalJson;
import com.secondline.contracts.Contracts;
import com.secondline.contracts.SchemaRegistry;
import com.secondline.contracts.generated.ErrorCode;
import com.secondline.gateway.GatewayApplication;
import com.secondline.gateway.GatewayException;
import com.secondline.gateway.TestKeys;
import com.secondline.gateway.pipeline.ToolCall;
import com.secondline.gateway.pipeline.ToolPipeline;
import com.secondline.gateway.pipeline.ToolResult;
import java.io.FileInputStream;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.yaml.snakeyaml.Yaml;

/** OM-05 Task 4 §10 REQ-004: the HTTP surface matches gateway-tools.yaml and only ever answers contract bodies. */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class OM_05_GatewayContractTest {
    static final Path CONTRACTS = Path.of(System.getProperty("contracts.root"));
    static final UUID RUN = UUID.fromString("22222222-2222-4222-8222-222222222222");
    static final SchemaRegistry SCHEMAS = SchemaRegistry.load();

    @DynamicPropertySource
    static void config(DynamicPropertyRegistry r) {
        r.add("gateway.signing-jwk-path", TestKeys::path);
        r.add("gateway.ledger-url", () -> "http://127.0.0.1:1");
        r.add("gateway.opa-url", () -> "http://127.0.0.1:1");
    }

    @Autowired
    TestRestTemplate http;

    @MockitoBean
    ToolPipeline pipeline;

    ResponseEntity<String> post(String path, String body, String auth) {
        HttpHeaders h = new HttpHeaders();
        h.setContentType(MediaType.APPLICATION_JSON);
        if (auth != null) h.set("Authorization", auth);
        return http.postForEntity(path, new HttpEntity<>(body, h), String.class);
    }

    static void contractError(ResponseEntity<String> r, ErrorCode code) {
        assertThat(r.getStatusCode().value()).isEqualTo(code.httpStatus().orElseThrow());
        JsonNode body = CanonicalJson.parse(r.getBody());
        assertThat(body.path("error_code").asText()).isEqualTo(code.name());
        assertThat(SCHEMAS.validate("error_response.schema.json", body)).isEmpty();
        assertThat(r.getBody()).doesNotContain("Exception").doesNotContain("at com.");
    }

    @Test
    @SuppressWarnings("unchecked")
    void OM_05_everyGatewayToolsPathIsServed() throws Exception {
        Map<String, Object> doc;
        try (var in = new FileInputStream(CONTRACTS.resolve("openapi/gateway-tools.yaml").toFile())) {
            doc = new Yaml().load(in);
        }
        List<String> toolPaths = new ArrayList<>();
        for (String p : ((Map<String, Object>) doc.get("paths")).keySet()) {
            if (p.startsWith("/v1/runs/{runId}/tools/")) toolPaths.add(p);
        }
        JsonNode index = CanonicalJson.parse(java.nio.file.Files.readString(CONTRACTS.resolve("tools/INDEX.json"))).path("tools");
        assertThat(toolPaths).hasSize(index.size()); // one path per §10 tool (19 in contracts 2.x)
        when(pipeline.handle(any())).thenReturn(new ToolResult(403,
                Contracts.MAPPER.readTree("{\"error_code\":\"PERMISSION_DENIED\",\"message\":\"x\",\"request_id\":\"" + UUID.randomUUID() + "\"}")));
        for (String p : toolPaths) {
            ResponseEntity<String> r = post(p.replace("{runId}", RUN.toString()), "{}", null);
            assertThat(r.getStatusCode().value()).as(p).isEqualTo(403);
        }
    }

    @Test
    void OM_05_controllerHandsThePipelineTheBareTokenAndRequestId() throws Exception {
        when(pipeline.handle(any())).thenReturn(new ToolResult(200, Contracts.MAPPER.readTree("{\"ok\":true}")));
        ResponseEntity<String> r = post("/v1/runs/" + RUN + "/tools/get_break", "{\"run_id\":\"" + RUN + "\"}", "Bearer abc.def.ghi");
        assertThat(r.getStatusCode().value()).isEqualTo(200);
        assertThat(r.getBody()).isEqualTo("{\"ok\":true}");
        ArgumentCaptor<ToolCall> c = ArgumentCaptor.forClass(ToolCall.class);
        verify(pipeline).handle(c.capture());
        assertThat(c.getValue().bearer()).isEqualTo("abc.def.ghi");
        assertThat(c.getValue().pathRunId()).isEqualTo(RUN);
        assertThat(c.getValue().tool()).isEqualTo("get_break");
        assertThat(c.getValue().body().path("run_id").asText()).isEqualTo(RUN.toString());
        assertThat(c.getValue().requestId()).isNotNull();
    }

    @Test
    void OM_05_missingOrNonBearerAuthIsAnEmptyToken() throws Exception {
        when(pipeline.handle(any())).thenReturn(new ToolResult(200, Contracts.MAPPER.readTree("{}")));
        post("/v1/runs/" + RUN + "/tools/get_break", "{}", "Basic dXNlcjpwYXNz");
        ArgumentCaptor<ToolCall> c = ArgumentCaptor.forClass(ToolCall.class);
        verify(pipeline).handle(c.capture());
        assertThat(c.getValue().bearer()).isEmpty(); // never a credential of another scheme
    }

    @Test
    void OM_05_malformedRunIdIsDeniedBeforeThePipeline() {
        contractError(post("/v1/runs/not-a-uuid/tools/get_break", "{}", "Bearer x"), ErrorCode.PERMISSION_DENIED);
        verify(pipeline, never()).handle(any());
    }

    @Test
    void OM_05_unreadableBodiesAreDomainInvalidBeforeThePipeline() {
        for (String bad : new String[] {"not json", "{\"a\":1,\"a\":2}", "{\"amount\":1.5}", "", "[1] [2]", "[]", "\"x\"", "null"}) {
            contractError(post("/v1/runs/" + RUN + "/tools/get_break", bad, "Bearer x"), ErrorCode.DOMAIN_INVALID);
        }
        verify(pipeline, never()).handle(any());
    }

    @Test
    void OM_05_typedPipelineFailureAndSurprisesAreContractErrors() {
        org.mockito.Mockito.doThrow(new GatewayException(ErrorCode.RUN_HALTED, "run halted")).when(pipeline).handle(any());
        contractError(post("/v1/runs/" + RUN + "/tools/get_break", "{}", "Bearer x"), ErrorCode.RUN_HALTED);
        org.mockito.Mockito.doThrow(new IllegalStateException("boom with secret abc.def.ghi")).when(pipeline).handle(any());
        ResponseEntity<String> r = post("/v1/runs/" + RUN + "/tools/get_break", "{}", "Bearer x");
        contractError(r, ErrorCode.RETRYABLE_UNAVAILABLE);
        assertThat(r.getBody()).doesNotContain("boom").doesNotContain("abc.def.ghi");
    }

    @Test
    void OM_05_unknownRouteIsAPlain404() {
        ResponseEntity<String> r = post("/v1/nothing/here", "{}", null);
        assertThat(r.getStatusCode().value()).isEqualTo(404);
        assertThat(r.getBody()).isNull();
    }

    @Test
    void OM_05_gatewayRefusesToStartWithoutItsKey() {
        // Command-line args: SpringApplicationBuilder.properties() are defaults that application.yml overrides.
        assertThatThrownBy(() -> new SpringApplicationBuilder(GatewayApplication.class)
                .run("--server.port=0", "--gateway.signing-jwk-path=/nonexistent/gateway-signing.jwk").close())
                .hasStackTraceContaining("cannot read signing key");
        assertThatThrownBy(() -> new SpringApplicationBuilder(GatewayApplication.class)
                .run("--server.port=0", "--gateway.signing-jwk-path=").close())
                .hasStackTraceContaining("gateway.signing-jwk-path");
    }
}
