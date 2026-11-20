package com.secondline.ledger.security;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.secondline.ledger.LedgerAuth;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** OM-07 insecure-defaults: a ledger that can't verify callers never starts; no default credential exists. */
class T_SEC_01_RealmConfigTest {
    @TempDir
    Path dir;

    @Test
    void T_SEC_01_gatewayTrustNeedsAPublicEd25519KeyWithKid() throws Exception {
        assertThatThrownBy(() -> GatewayTrust.load("")).hasMessageContaining("LEDGER_GATEWAY_JWK_PATH");
        assertThatThrownBy(() -> GatewayTrust.load(dir.resolve("missing.jwk").toString())).hasMessageContaining("missing.jwk");
        Path priv = Files.writeString(dir.resolve("priv.jwk"), LedgerAuth.SERVICE.privateJwk().toJSONString());
        assertThatThrownBy(() -> GatewayTrust.load(priv.toString())).hasMessageContaining("private");
        Path rsa = Files.writeString(dir.resolve("rsa.jwk"), "{\"kty\":\"RSA\",\"n\":\"AQAB\",\"e\":\"AQAB\",\"kid\":\"x\"}");
        assertThatThrownBy(() -> GatewayTrust.load(rsa.toString())).isInstanceOf(IllegalStateException.class);
        Path noKid = Files.writeString(dir.resolve("nokid.jwk"),
                LedgerAuth.SERVICE.publicJwk().toJSONString().replaceAll("\"kid\":\"[^\"]*\",?", "").replace(",}", "}"));
        assertThatThrownBy(() -> GatewayTrust.load(noKid.toString())).hasMessageContaining("kid");
        assertThat(GatewayTrust.load(LedgerAuth.publicJwkPath()).kid()).isEqualTo(LedgerAuth.SERVICE.kid());
    }

    @Test
    void T_SEC_01_operatorCredentialHasNoDefault() {
        assertThatThrownBy(() -> new OperatorCredential("")).hasMessageContaining("LEDGER_OPERATOR_TOKEN");
        assertThatThrownBy(() -> new OperatorCredential("short-secret")).hasMessageContaining("32");
        OperatorCredential op = new OperatorCredential(LedgerAuth.OPERATOR);
        assertThat(op.matches(LedgerAuth.OPERATOR)).isTrue();
        assertThat(op.matches(LedgerAuth.OPERATOR + " ")).isFalse();
        assertThat(op.matches(null)).isFalse();
        assertThat(op.toString()).doesNotContain(LedgerAuth.OPERATOR);
    }

    @Test
    void T_SEC_01_clockSkewIsThirtySeconds() {
        UUID ns = UUID.randomUUID();
        String token = LedgerAuth.service(ns); // exp = now + 60 s
        Instant now = Instant.now();
        ServiceTokenVerifier at = new ServiceTokenVerifier(GatewayTrust.load(LedgerAuth.publicJwkPath()),
                Clock.fixed(now.plusSeconds(85), ZoneOffset.UTC));
        assertThat(at.verify(token)).contains(ns);
        ServiceTokenVerifier late = new ServiceTokenVerifier(GatewayTrust.load(LedgerAuth.publicJwkPath()),
                Clock.fixed(now.plusSeconds(95), ZoneOffset.UTC));
        assertThat(late.verify(token)).isEmpty();
    }
}
