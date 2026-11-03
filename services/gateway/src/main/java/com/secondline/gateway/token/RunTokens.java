package com.secondline.gateway.token;

import com.nimbusds.jose.JOSEException;
import com.nimbusds.jose.JOSEObjectType;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.Ed25519Signer;
import com.nimbusds.jose.crypto.Ed25519Verifier;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import com.secondline.contracts.generated.ErrorCode;
import com.secondline.gateway.GatewayException;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Date;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/**
 * Issues and verifies run tokens (OM-05 G2 G3, §11 identity scheme, ADR-013, ADR-015).
 *
 * <p>{@link #issue} and {@link #verify} (learn card; written by Claude at Om's request, 2026-11-03). The spec is
 * {@code OM_05_RunTokensTest}; the rules:
 * <ul>
 *   <li>Compact JWS, header {@code alg=EdDSA}, {@code kid} = {@link SigningKeys#kid()}, {@code typ=JWT}.</li>
 *   <li>Claims: {@code iss}={@link #ISSUER}, {@code aud}={@link #AUDIENCE}, {@code sub}=agent_id, {@code run_id},
 *       {@code ns}, {@code scenario_id}, {@code controls}, {@code allowed_tools}, {@code iat}, {@code nbf},
 *       {@code exp} = now + ttl, {@code jti} = a fresh UUID.</li>
 *   <li>verify: accept only if the alg is exactly EdDSA, the kid is ours, the signature verifies, iss and aud match,
 *       exp/nbf hold within {@link #SKEW}, every claim above is present and well-formed, the run_id claim equals
 *       {@code pathRunId}, and {@code tool} is in allowed_tools.</li>
 *   <li>Every failure throws {@link #denied()}: one code, one message, so a caller can't learn which check failed.</li>
 * </ul>
 */
public class RunTokens {
    public static final String ISSUER = "secondline-gateway";
    public static final String AUDIENCE = "secondline-gateway-tools";
    public static final Duration SKEW = Duration.ofSeconds(30);
    private static final Set<String> CONTROLS = Set.of("off", "monitor", "full");
    /** Explicit typing (RFC 8725 §3.11): a service JWT signed by the same key can never pass as a run token. */
    public static final JOSEObjectType TYPE = new JOSEObjectType("sl-run+jwt");

    private final SigningKeys keys;
    private final Clock clock;
    private final Duration ttl;

    public RunTokens(SigningKeys keys, Clock clock, Duration ttl) {
        this.keys = keys;
        this.clock = clock;
        this.ttl = ttl;
    }

    public SignedToken issue(RunGrant grant) {
        Instant now = clock.instant();
        Instant exp = now.plus(ttl);
        JWTClaimsSet claims = new JWTClaimsSet.Builder()
                .issuer(ISSUER).audience(AUDIENCE).subject(grant.agentId())
                .claim("run_id", grant.runId().toString()).claim("ns", grant.ns().toString())
                .claim("scenario_id", grant.scenarioId()).claim("controls", grant.controls())
                .claim("allowed_tools", grant.allowedTools())
                .issueTime(Date.from(now)).notBeforeTime(Date.from(now)).expirationTime(Date.from(exp))
                .jwtID(UUID.randomUUID().toString()).build();
        SignedJWT jwt = new SignedJWT(new JWSHeader.Builder(JWSAlgorithm.EdDSA).keyID(keys.kid()).type(TYPE).build(), claims);
        try {
            jwt.sign(new Ed25519Signer(keys.privateJwk()));
        } catch (JOSEException e) {
            throw new IllegalStateException("cannot sign a run token", e);
        }
        // exp is carried in whole seconds; report the same instant the token holds.
        return new SignedToken(jwt.serialize(), exp.truncatedTo(ChronoUnit.SECONDS));
    }

    /**
     * Accepts only our own EdDSA tokens for this run and tool, inside their lifetime ± {@link #SKEW}. The order is
     * deliberate: algorithm and kid before any signature work, the signature (with OUR public key, never a key named
     * in the token) before trusting any claim, then every claim. Anything at all that goes wrong is {@link #denied()}.
     */
    public RunClaims verify(String token, UUID pathRunId, String tool) {
        try {
            if (token == null || pathRunId == null || tool == null) throw denied();
            SignedJWT jwt = SignedJWT.parse(token); // a PlainJWT ("alg":"none") isn't a JWS and fails here
            JWSHeader h = jwt.getHeader();
            if (!JWSAlgorithm.EdDSA.equals(h.getAlgorithm()) || !keys.kid().equals(h.getKeyID()) || !TYPE.equals(h.getType())) {
                throw denied();
            }
            if (!jwt.verify(new Ed25519Verifier(keys.publicJwk()))) throw denied();
            JWTClaimsSet c = jwt.getJWTClaimsSet();
            Instant now = clock.instant();
            if (!ISSUER.equals(c.getIssuer()) || !List.of(AUDIENCE).equals(c.getAudience())) throw denied();
            Date exp = c.getExpirationTime();
            Date nbf = c.getNotBeforeTime();
            if (exp == null || nbf == null || c.getIssueTime() == null || c.getJWTID() == null) throw denied();
            if (now.isAfter(exp.toInstant().plus(SKEW)) || nbf.toInstant().isAfter(now.plus(SKEW))
                    || c.getIssueTime().toInstant().isAfter(now.plus(SKEW))) {
                throw denied();
            }
            UUID runId = UUID.fromString(c.getStringClaim("run_id"));
            UUID ns = UUID.fromString(c.getStringClaim("ns"));
            String scenario = c.getStringClaim("scenario_id");
            String controls = c.getStringClaim("controls");
            String agent = c.getSubject();
            List<String> tools = c.getStringListClaim("allowed_tools");
            if (scenario == null || scenario.isBlank() || agent == null || agent.isBlank() || tools == null || tools.isEmpty()
                    || !CONTROLS.contains(controls)) {
                throw denied();
            }
            if (!runId.equals(pathRunId) || !tools.contains(tool)) throw denied();
            return new RunClaims(runId, ns, scenario, agent, controls, Set.copyOf(tools), exp.toInstant());
        } catch (GatewayException e) {
            throw e;
        } catch (RuntimeException | java.text.ParseException | JOSEException e) {
            throw denied(); // malformed JSON, wrong claim types, null claims, bad UUIDs: all the same refusal
        }
    }

    /** The only error verify() may throw. */
    public static GatewayException denied() {
        return new GatewayException(ErrorCode.PERMISSION_DENIED, "run token not accepted for this run and tool");
    }
}
