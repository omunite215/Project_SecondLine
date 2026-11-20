package com.secondline.ledger;

import com.nimbusds.jose.JOSEObjectType;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.Ed25519Signer;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import com.secondline.gateway.client.ServiceTokens;
import com.secondline.gateway.token.SigningKeys;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Clock;
import java.time.Instant;
import java.util.Date;
import java.util.UUID;
import java.util.function.UnaryOperator;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.test.context.DynamicPropertyRegistry;

/**
 * OM-07 test credentials for a booted ledger: the gateway's service key (the ledger trusts only its public half), the
 * gateway's separate run-token key (never trusted by the ledger), and an operator bearer. Real ones come from make bootstrap.
 */
public final class LedgerAuth {
    public static final SigningKeys SERVICE = SigningKeys.generate("gw-svc-test000001");
    public static final SigningKeys RUN = SigningKeys.generate("gw-run-test000001");
    public static final String OPERATOR = "op-test-" + "0123456789abcdef".repeat(3);
    private static Path publicJwk;

    private LedgerAuth() {}

    public static synchronized String publicJwkPath() {
        if (publicJwk == null) {
            try {
                publicJwk = Files.createTempFile("gateway-service", ".pub.jwk");
                Files.writeString(publicJwk, SERVICE.publicJwk().toJSONString());
                publicJwk.toFile().deleteOnExit();
            } catch (IOException e) {
                throw new UncheckedIOException(e);
            }
        }
        return publicJwk.toString();
    }

    public static void register(DynamicPropertyRegistry r) {
        r.add("ledger.auth.gateway-jwk-path", LedgerAuth::publicJwkPath);
        r.add("ledger.auth.operator-token", () -> OPERATOR);
    }

    /** What the real gateway sends: the producer's own code, so a claim drift breaks this test. */
    public static String service(UUID ns) {
        return new ServiceTokens(SERVICE, Clock.systemUTC()).bearer(ns);
    }

    public static HttpHeaders bearer(String token) {
        HttpHeaders h = new HttpHeaders();
        h.setContentType(MediaType.APPLICATION_JSON);
        if (token != null) h.setBearerAuth(token);
        return h;
    }

    public static HttpHeaders operator() {
        return bearer(OPERATOR);
    }

    /** A service-shaped token with one thing changed: the base claims are exactly what ServiceTokens issues. */
    public static String forge(SigningKeys key, JOSEObjectType type, UUID ns, UnaryOperator<JWTClaimsSet.Builder> change) {
        Instant now = Instant.now();
        JWTClaimsSet.Builder claims = new JWTClaimsSet.Builder()
                .issuer("secondline-gateway").subject("gateway").audience("ledger")
                .issueTime(Date.from(now)).notBeforeTime(Date.from(now)).expirationTime(Date.from(now.plusSeconds(60)))
                .jwtID(UUID.randomUUID().toString()).claim("ns", ns.toString());
        SignedJWT jwt = new SignedJWT(new JWSHeader.Builder(JWSAlgorithm.EdDSA).keyID(key.kid()).type(type).build(),
                change.apply(claims).build());
        try {
            jwt.sign(new Ed25519Signer(key.privateJwk()));
        } catch (com.nimbusds.jose.JOSEException e) {
            throw new IllegalStateException(e);
        }
        return jwt.serialize();
    }
}
