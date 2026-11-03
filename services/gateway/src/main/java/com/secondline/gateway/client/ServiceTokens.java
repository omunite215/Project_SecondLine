package com.secondline.gateway.client;

import com.nimbusds.jose.JOSEException;
import com.nimbusds.jose.JOSEObjectType;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.Ed25519Signer;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import com.secondline.gateway.token.SigningKeys;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Date;
import java.util.UUID;

/** G12: a fresh 60 s service JWT per ledger call (aud=ledger, sub=gateway). The ledger verifies it in OM-07. */
public final class ServiceTokens {
    static final Duration TTL = Duration.ofSeconds(60);
    /** Explicit typing (RFC 8725 §3.11), distinct from run tokens; OM-07's ledger verifier must check it. */
    public static final JOSEObjectType TYPE = new JOSEObjectType("sl-svc+jwt");
    private final SigningKeys keys;
    private final Clock clock;

    public ServiceTokens(SigningKeys keys, Clock clock) {
        this.keys = keys;
        this.clock = clock;
    }

    public String bearer() {
        Instant now = clock.instant();
        JWTClaimsSet claims = new JWTClaimsSet.Builder()
                .issuer("secondline-gateway").subject("gateway").audience("ledger")
                .issueTime(Date.from(now)).notBeforeTime(Date.from(now)).expirationTime(Date.from(now.plus(TTL)))
                .jwtID(UUID.randomUUID().toString()).build();
        SignedJWT jwt = new SignedJWT(new JWSHeader.Builder(JWSAlgorithm.EdDSA).keyID(keys.kid()).type(TYPE).build(), claims);
        try {
            jwt.sign(new Ed25519Signer(keys.privateJwk()));
        } catch (JOSEException e) {
            throw new IllegalStateException("cannot sign the service token", e);
        }
        return jwt.serialize();
    }
}
