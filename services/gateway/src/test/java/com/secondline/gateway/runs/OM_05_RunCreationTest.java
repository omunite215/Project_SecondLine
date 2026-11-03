package com.secondline.gateway.runs;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.secondline.contracts.CanonicalJson;
import com.secondline.contracts.Contracts;
import com.secondline.contracts.SchemaRegistry;
import com.secondline.contracts.generated.ErrorCode;
import com.secondline.gateway.GatewayException;
import com.secondline.gateway.client.LedgerClient;
import com.secondline.gateway.client.LedgerResponse;
import com.secondline.gateway.route.ToolRoute;
import com.secondline.gateway.route.ToolRoutes;
import com.secondline.gateway.token.RunGrant;
import com.secondline.gateway.token.RunTokens;
import com.secondline.gateway.token.SignedToken;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

/** OM-05 Task 5 G5 G6 §11: POST /v1/runs. Operator-only, schema-checked, idempotent, bound to the ledger's run. */
class OM_05_RunCreationTest {
    static final String OPERATOR = "o".repeat(43);
    static final UUID NS = UUID.fromString("11111111-1111-4111-8111-111111111111");
    static final UUID RUN = UUID.fromString("22222222-2222-4222-8222-222222222222");
    static final String IDEMPOTENCY_ID = "5c4b3a29-1807-4f6e-9d5c-4b3a29180716";
    static final SignedToken TOKEN = new SignedToken("a".repeat(40) + ".b.c", Instant.parse("2026-11-03T12:30:00Z"));

    RunTokens tokens = mock(RunTokens.class);
    LedgerClient ledger = mock(LedgerClient.class);
    RunService runs;

    @BeforeEach
    void wire() {
        runs = new RunService(OPERATOR, ledger, tokens, SchemaRegistry.load(), 4);
        when(ledger.registerRun(any())).thenReturn(new LedgerResponse(201, Contracts.MAPPER.createObjectNode()
                .put("run_id", RUN.toString()).put("ns", NS.toString()).put("controls", "monitor")));
        when(tokens.issue(any())).thenReturn(TOKEN);
    }

    static ObjectNode request() {
        return Contracts.MAPPER.createObjectNode().put("ns", NS.toString()).put("controls", "monitor")
                .put("agent_id", "agt_00000001").put("scenario_id", "scn_00000042")
                .put("manifest_ref", "experiments/manifests/pilot-001.json");
    }

    static void code(ErrorCode c, Runnable r) {
        assertThatThrownBy(r::run).isInstanceOf(GatewayException.class).extracting(e -> ((GatewayException) e).code()).isEqualTo(c);
    }

    @Test
    void OM_05_operatorTokenRequired() {
        for (String bad : new String[] {null, "", "wrong", OPERATOR + "x", OPERATOR.substring(1)}) {
            code(ErrorCode.PERMISSION_DENIED, () -> runs.create(bad, IDEMPOTENCY_ID, request()));
        }
        RunService unset = new RunService("", ledger, tokens, SchemaRegistry.load(), 4);
        code(ErrorCode.PERMISSION_DENIED, () -> unset.create("", IDEMPOTENCY_ID, request())); // unset secret denies everyone
        verify(ledger, never()).registerRun(any());
    }

    @Test
    void OM_05_idempotencyKeyIsARequiredUuid() {
        code(ErrorCode.DOMAIN_INVALID, () -> runs.create(OPERATOR, null, request()));
        code(ErrorCode.DOMAIN_INVALID, () -> runs.create(OPERATOR, "not-a-uuid", request()));
        verify(ledger, never()).registerRun(any());
    }

    @Test
    void OM_05_runRequestIsSchemaChecked() {
        ObjectNode bad = request();
        bad.put("controls", "everything");
        code(ErrorCode.DOMAIN_INVALID, () -> runs.create(OPERATOR, IDEMPOTENCY_ID, bad));
        ObjectNode extra = request();
        extra.put("allowed_tools", "drop_tables"); // a caller can't widen the grant
        code(ErrorCode.DOMAIN_INVALID, () -> runs.create(OPERATOR, IDEMPOTENCY_ID, extra));
        verify(ledger, never()).registerRun(any());
    }

    @Test
    void OM_05_tokenIsBoundToTheLedgerRegisteredRun() {
        RunService.Created c = runs.create(OPERATOR, IDEMPOTENCY_ID, request());
        assertThat(c.status()).isEqualTo(201);
        assertThat(SchemaRegistry.load().validate("runs/run_token.schema.json", c.body())).isEmpty();
        assertThat(c.body().path("run_id").asText()).isEqualTo(RUN.toString());
        assertThat(c.body().path("token").asText()).isEqualTo(TOKEN.token());
        ArgumentCaptor<JsonNode> reg = ArgumentCaptor.forClass(JsonNode.class);
        verify(ledger).registerRun(reg.capture());
        assertThat(CanonicalJson.canonicalize(reg.getValue())).isEqualTo(CanonicalJson.canonicalize(
                Contracts.MAPPER.createObjectNode().put("ns", NS.toString()).put("controls", "monitor")
                        .put("agent_id", "agt_00000001").put("manifest_ref", "experiments/manifests/pilot-001.json")));
        ArgumentCaptor<RunGrant> grant = ArgumentCaptor.forClass(RunGrant.class);
        verify(tokens).issue(grant.capture());
        RunGrant g = grant.getValue();
        assertThat(g.runId()).isEqualTo(RUN);
        assertThat(g.ns()).isEqualTo(NS);
        assertThat(g.scenarioId()).isEqualTo("scn_00000042");
        assertThat(g.agentId()).isEqualTo("agt_00000001");
        assertThat(g.controls()).isEqualTo("monitor"); // from the ledger's record, never trusted from the caller alone
        assertThat(g.allowedTools()).containsExactlyElementsOf(ToolRoutes.all().stream().map(ToolRoute::tool).sorted().toList());
    }

    @Test
    void OM_05_ledgerRefusalPassesThroughAndNoTokenIsIssued() throws Exception {
        JsonNode denied = CanonicalJson.parse("{\"error_code\":\"PERMISSION_DENIED\",\"message\":\"ns not loaded\",\"request_id\":\"" + UUID.randomUUID() + "\"}");
        when(ledger.registerRun(any())).thenReturn(new LedgerResponse(403, denied));
        RunService.Created c = runs.create(OPERATOR, IDEMPOTENCY_ID, request());
        assertThat(c.status()).isEqualTo(403);
        assertThat(c.body()).isEqualTo(denied);
        verify(tokens, never()).issue(any());
    }

    @Test
    void OM_05_sameKeySameBodyReturnsTheSameToken() {
        RunService.Created first = runs.create(OPERATOR, IDEMPOTENCY_ID, request());
        RunService.Created again = runs.create(OPERATOR, IDEMPOTENCY_ID, request());
        assertThat(again.body()).isEqualTo(first.body());
        verify(ledger, times(1)).registerRun(any());
        verify(tokens, times(1)).issue(any());
    }

    @Test
    void OM_05_sameKeyDifferentBodyIsIdempotencyConflict() {
        runs.create(OPERATOR, IDEMPOTENCY_ID, request());
        ObjectNode other = request();
        other.put("controls", "full");
        code(ErrorCode.IDEMPOTENCY_CONFLICT, () -> runs.create(OPERATOR, IDEMPOTENCY_ID, other));
        verify(ledger, times(1)).registerRun(any());
    }

    @Test
    void OM_05_idempotencyMemoryIsBounded() {
        for (int i = 0; i < 6; i++) runs.create(OPERATOR, UUID.randomUUID().toString(), request());
        assertThat(runs.rememberedKeys()).isLessThanOrEqualTo(4); // capacity 4 here; oldest evicted (documented limit)
    }
}
