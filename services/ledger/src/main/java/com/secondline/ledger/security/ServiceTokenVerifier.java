package com.secondline.ledger.security;

import com.nimbusds.jose.JOSEException;
import com.nimbusds.jose.JOSEObjectType;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.Ed25519Verifier;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import java.text.ParseException;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Date;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * Verifies the gateway's per-call service JWT (OM-05 G12, OM-07). Order is deliberate: header (EdDSA, our kid,
 * typ sl-svc+jwt, no critical params) before any signature work, then the signature with the trusted key only
 * (never a key named in the token), then iss/sub/aud exactly, time with 30 s skew and at most 5 min lifetime, and
 * a canonical ns UUID. Any doubt is empty: the caller answers PERMISSION_DENIED and nothing runs.
 */
public final class ServiceTokenVerifier {
    static final JOSEObjectType TYPE = new JOSEObjectType("sl-svc+jwt");
    static final String ISSUER = "secondline-gateway";
    static final String SUBJECT = "gateway";
    static final String AUDIENCE = "ledger";
    static final Duration SKEW = Duration.ofSeconds(30);
    static final Duration MAX_LIFETIME = Duration.ofMinutes(5);

    private final GatewayTrust trust;
    private final Clock clock;

    public ServiceTokenVerifier(GatewayTrust trust, Clock clock) {
        this.trust = trust;
        this.clock = clock;
    }

    /** The ns the token is scoped to, or empty if the token is anything but a valid gateway service token. */
    public Optional<UUID> verify(String token) {
        if (token == null || token.isEmpty()) return Optional.empty();
        try {
            SignedJWT jwt = SignedJWT.parse(token);
            JWSHeader h = jwt.getHeader();
            if (!JWSAlgorithm.EdDSA.equals(h.getAlgorithm()) || !trust.kid().equals(h.getKeyID()) || !TYPE.equals(h.getType())
                    || (h.getCriticalParams() != null && !h.getCriticalParams().isEmpty())) {
                return Optional.empty();
            }
            if (!jwt.verify(new Ed25519Verifier(trust.publicJwk()))) return Optional.empty();
            JWTClaimsSet c = jwt.getJWTClaimsSet();
            if (!ISSUER.equals(c.getIssuer()) || !SUBJECT.equals(c.getSubject()) || !List.of(AUDIENCE).equals(c.getAudience())) {
                return Optional.empty();
            }
            if (!timely(c.getIssueTime(), c.getNotBeforeTime(), c.getExpirationTime(), clock.instant())) return Optional.empty();
            if (!(c.getClaim("ns") instanceof String raw)) return Optional.empty();
            UUID ns = UUID.fromString(raw);
            return ns.toString().equals(raw) ? Optional.of(ns) : Optional.empty(); // canonical form only
        } catch (ParseException | JOSEException | IllegalArgumentException e) {
            return Optional.empty();
        }
    }

    private static boolean timely(Date iat, Date nbf, Date exp, Instant now) {
        if (iat == null || exp == null) return false;
        if (now.isAfter(exp.toInstant().plus(SKEW))) return false;
        if (nbf != null && now.plus(SKEW).isBefore(nbf.toInstant())) return false;
        if (iat.toInstant().isAfter(now.plus(SKEW))) return false;
        return Duration.between(iat.toInstant(), exp.toInstant()).compareTo(MAX_LIFETIME) <= 0;
    }
}
