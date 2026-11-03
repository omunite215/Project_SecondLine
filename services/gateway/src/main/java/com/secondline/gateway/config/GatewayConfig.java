package com.secondline.gateway.config;

import com.secondline.contracts.SchemaRegistry;
import com.secondline.gateway.client.DecisionLog;
import com.secondline.gateway.client.LedgerClient;
import com.secondline.gateway.client.PolicyClient;
import com.secondline.gateway.client.ServiceTokens;
import com.secondline.gateway.guard.InMemoryRunGuard;
import com.secondline.gateway.guard.RunGuard;
import com.secondline.gateway.pipeline.ToolPipeline;
import com.secondline.gateway.runs.RunService;
import com.secondline.gateway.schema.InputSchemas;
import com.secondline.gateway.token.RunTokens;
import com.secondline.gateway.token.SigningKeys;
import java.nio.file.Path;
import java.time.Clock;
import java.time.Duration;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Wires the pipeline stages (OM-05). The signing key is loaded at startup: an unset, missing or unreadable key
 * stops the gateway (G4). Dependency URLs come from compose (GATEWAY_LEDGER_URL, GATEWAY_OPA_URL).
 */
@Configuration
public class GatewayConfig {

    @Bean
    Clock clock() {
        return Clock.systemUTC();
    }

    @Bean
    SigningKeys signingKeys(@Value("${gateway.signing-jwk-path:}") String path) {
        if (path.isBlank()) throw new IllegalStateException("gateway.signing-jwk-path (GATEWAY_SIGNING_JWK_PATH) is not set");
        return SigningKeys.load(Path.of(path));
    }

    @Bean
    RunTokens runTokens(SigningKeys keys, Clock clock, @Value("${gateway.run-token.ttl:30m}") Duration ttl) {
        return new RunTokens(keys, clock, ttl);
    }

    @Bean
    LedgerClient ledgerClient(SigningKeys keys, Clock clock, @Value("${gateway.ledger-url}") String url,
                              @Value("${gateway.ledger-timeout:2s}") Duration timeout) {
        return new LedgerClient(url, new ServiceTokens(keys, clock), timeout);
    }

    @Bean
    PolicyClient policyClient(@Value("${gateway.opa-url}") String url, @Value("${gateway.opa-timeout:200ms}") Duration timeout) {
        return new PolicyClient(url, timeout);
    }

    @Bean
    SchemaRegistry schemaRegistry() {
        return SchemaRegistry.load();
    }

    @Bean
    DecisionLog decisionLog(LedgerClient ledger, SchemaRegistry schemas) {
        return new DecisionLog(ledger, schemas);
    }

    /** G10 harness caps; max-messages is ADR-014's C_msg placeholder until OM-12 sets it per run. */
    @Bean
    RunGuard runGuard(@Value("${gateway.budget.max-calls:500}") int maxCalls, @Value("${gateway.budget.max-messages:5}") int maxMessages) {
        return new InMemoryRunGuard(maxCalls, maxMessages);
    }

    /** G5: an unset GATEWAY_OPERATOR_TOKEN denies every run creation. */
    @Bean
    RunService runService(@Value("${gateway.operator-token:}") String operatorToken, LedgerClient ledger, RunTokens tokens,
                          SchemaRegistry schemas, @Value("${gateway.idempotency.capacity:10000}") int capacity) {
        return new RunService(operatorToken, ledger, tokens, schemas, capacity);
    }

    @Bean
    ToolPipeline toolPipeline(RunTokens tokens, SchemaRegistry schemas, RunGuard guard, PolicyClient policy,
                              LedgerClient ledger, DecisionLog log, Clock clock) {
        return new ToolPipeline(tokens, new InputSchemas(schemas), guard, policy, ledger, log, clock);
    }
}
