package com.secondline.gateway.token;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;

import com.nimbusds.jose.JOSEObjectType;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.Ed25519Signer;
import com.nimbusds.jose.crypto.MACSigner;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.PlainJWT;
import com.nimbusds.jwt.SignedJWT;
import com.secondline.contracts.generated.ErrorCode;
import com.secondline.gateway.GatewayException;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Date;
import java.util.List;
import java.util.UUID;
import java.util.function.Consumer;
import org.junit.jupiter.api.Test;

/**
 * OM-05 G2 G3 §11 SEC-03 ADR-013 ADR-015: the spec for Om's RunTokens. A token is accepted only for its own run,
 * its own tools and its own lifetime, signed by our key with EdDSA; every other token gets the same refusal.
 */
class OM_05_RunTokensTest {
    static final Instant T0 = Instant.parse("2026-03-02T16:00:00Z");
    static final SigningKeys KEYS = SigningKeys.generate("gw-0000000000000001");
    static final UUID RUN = UUID.fromString("3f2e1d0c-4b5a-4968-8776-655443322110");
    static final UUID NS = UUID.fromString("6a5b4c3d-2e1f-4a0b-9c8d-7e6f5a4b3c2d");
    static final List<String> TOOLS = List.of("read_trade", "propose_adjustment");
    static final RunGrant GRANT = new RunGrant(RUN, NS, "scn_0000A001", "agt_run3f2e1d0c", "full", TOOLS);

    /** A clock the test moves. */
    static final class MovingClock extends Clock {
        Instant now = T0;

        @Override public ZoneOffset getZone() { return ZoneOffset.UTC; }
        @Override public Clock withZone(java.time.ZoneId z) { return this; }
        @Override public Instant instant() { return now; }
    }

    final MovingClock clock = new MovingClock();
    final RunTokens tokens = new RunTokens(KEYS, clock, Duration.ofMinutes(30));

    static GatewayException refused(Runnable r) {
        Throwable t = catchThrowable(r::run);
        assertThat(t).as("must refuse with the one typed error").isInstanceOf(GatewayException.class);
        GatewayException e = (GatewayException) t;
        assertThat(e.code()).isEqualTo(ErrorCode.PERMISSION_DENIED);
        return e;
    }

    /** The claims a correct token carries, for crafting tokens the gateway must refuse. */
    static JWTClaimsSet.Builder validClaims() {
        return new JWTClaimsSet.Builder()
                .issuer(RunTokens.ISSUER).audience(RunTokens.AUDIENCE).subject("agt_run3f2e1d0c")
                .claim("run_id", RUN.toString()).claim("ns", NS.toString()).claim("scenario_id", "scn_0000A001")
                .claim("controls", "full").claim("allowed_tools", TOOLS)
                .issueTime(Date.from(T0)).notBeforeTime(Date.from(T0)).expirationTime(Date.from(T0.plusSeconds(1800)))
                .jwtID(UUID.randomUUID().toString());
    }

    static String signEd(SigningKeys keys, String kid, Consumer<JWTClaimsSet.Builder> edit) {
        try {
            JWTClaimsSet.Builder b = validClaims();
            edit.accept(b);
            SignedJWT jwt = new SignedJWT(new JWSHeader.Builder(JWSAlgorithm.EdDSA).keyID(kid).type(JOSEObjectType.JWT).build(), b.build());
            jwt.sign(new Ed25519Signer(keys.privateJwk()));
            return jwt.serialize();
        } catch (Exception e) {
            throw new IllegalStateException(e);
        }
    }

    // ---- the happy path -------------------------------------------------------------------------------------

    @Test
    void OM_05_issuedTokenVerifies() {
        SignedToken t = tokens.issue(GRANT);
        assertThat(t.expiresAt()).isEqualTo(T0.plus(Duration.ofMinutes(30)));
        RunClaims c = tokens.verify(t.token(), RUN, "read_trade");
        assertThat(c).isEqualTo(new RunClaims(RUN, NS, "scn_0000A001", "agt_run3f2e1d0c", "full",
                java.util.Set.copyOf(TOOLS), T0.plus(Duration.ofMinutes(30))));
    }

    @Test
    void OM_05_issuedTokenHasTheG2HeaderAndClaims() throws Exception {
        SignedJWT jwt = SignedJWT.parse(tokens.issue(GRANT).token());
        assertThat(jwt.getHeader().getAlgorithm()).isEqualTo(JWSAlgorithm.EdDSA);
        assertThat(jwt.getHeader().getKeyID()).isEqualTo(KEYS.kid());
        assertThat(jwt.getHeader().getType()).isEqualTo(JOSEObjectType.JWT);
        JWTClaimsSet c = jwt.getJWTClaimsSet();
        assertThat(c.getIssuer()).isEqualTo(RunTokens.ISSUER);
        assertThat(c.getAudience()).containsExactly(RunTokens.AUDIENCE);
        assertThat(c.getSubject()).isEqualTo("agt_run3f2e1d0c");
        assertThat(c.getStringClaim("run_id")).isEqualTo(RUN.toString());
        assertThat(c.getStringClaim("ns")).isEqualTo(NS.toString());
        assertThat(c.getStringClaim("scenario_id")).isEqualTo("scn_0000A001");
        assertThat(c.getStringClaim("controls")).isEqualTo("full");
        assertThat(c.getStringListClaim("allowed_tools")).containsExactlyElementsOf(TOOLS);
        assertThat(c.getIssueTime().toInstant()).isEqualTo(T0);
        assertThat(c.getNotBeforeTime().toInstant()).isEqualTo(T0);
        assertThat(c.getJWTID()).isNotBlank();
        assertThat(tokens.issue(GRANT).token()).as("jti is fresh per token").isNotEqualTo(tokens.issue(GRANT).token());
    }

    // ---- refusals (Review Focus 1, 2, 5) -------------------------------------------------------------------

    @Test
    void OM_05_tokenAlgorithmConfusionRejected() throws Exception {
        String none = new PlainJWT(validClaims().build()).serialize();
        refused(() -> tokens.verify(none, RUN, "read_trade"));
        // HS256 "signed" with our public key bytes: the classic confusion attack.
        byte[] pub = Base64.getUrlDecoder().decode(KEYS.publicJwk().getX().toString());
        SignedJWT hs = new SignedJWT(new JWSHeader.Builder(JWSAlgorithm.HS256).keyID(KEYS.kid()).build(), validClaims().build());
        hs.sign(new MACSigner(pub));
        refused(() -> tokens.verify(hs.serialize(), RUN, "read_trade"));
        // Another key: under our kid (signature fails) and under its own kid (unknown kid).
        SigningKeys other = SigningKeys.generate("gw-ffffffffffffffff");
        refused(() -> tokens.verify(signEd(other, KEYS.kid(), b -> {}), RUN, "read_trade"));
        refused(() -> tokens.verify(signEd(other, other.kid(), b -> {}), RUN, "read_trade"));
    }

    @Test
    void OM_05_craftedValidTokenIsAccepted() {
        // Guards the refusal tests: signEd with our key and kid builds a token verify() must accept.
        assertThat(tokens.verify(signEd(KEYS, KEYS.kid(), b -> {}), RUN, "read_trade").runId()).isEqualTo(RUN);
    }

    @Test
    void OM_05_tamperedPayloadRejected() {
        String[] parts = tokens.issue(GRANT).token().split("\\.");
        String other = new String(Base64.getUrlDecoder().decode(parts[1])).replace(NS.toString(), UUID.randomUUID().toString());
        String forged = parts[0] + "." + Base64.getUrlEncoder().withoutPadding().encodeToString(other.getBytes()) + "." + parts[2];
        refused(() -> tokens.verify(forged, RUN, "read_trade"));
    }

    @Test
    void OM_05_wrongAudienceOrIssuerRejected() {
        refused(() -> tokens.verify(signEd(KEYS, KEYS.kid(), b -> b.audience("ledger")), RUN, "read_trade"));
        refused(() -> tokens.verify(signEd(KEYS, KEYS.kid(), b -> b.issuer("someone-else")), RUN, "read_trade"));
    }

    @Test
    void OM_05_expiryWithSkew() {
        SignedToken t = tokens.issue(GRANT);
        clock.now = t.expiresAt().plusSeconds(29);
        assertThat(tokens.verify(t.token(), RUN, "read_trade").runId()).isEqualTo(RUN);
        clock.now = t.expiresAt().plusSeconds(31);
        refused(() -> tokens.verify(t.token(), RUN, "read_trade"));
    }

    @Test
    void OM_05_notBeforeInFutureRejected() {
        refused(() -> tokens.verify(signEd(KEYS, KEYS.kid(), b -> b.notBeforeTime(Date.from(T0.plusSeconds(60)))), RUN, "read_trade"));
    }

    @Test
    void OM_05_pathRunIdMustMatchClaim() {
        String t = tokens.issue(GRANT).token();
        refused(() -> tokens.verify(t, UUID.randomUUID(), "read_trade"));
    }

    @Test
    void OM_05_toolOutsideAllowedToolsRejected() {
        String t = tokens.issue(new RunGrant(RUN, NS, "scn_0000A001", "agt_run3f2e1d0c", "off", List.of("read_trade"))).token();
        refused(() -> tokens.verify(t, RUN, "propose_adjustment"));
    }

    @Test
    void OM_05_missingOrMalformedClaimsRejected() {
        for (String claim : List.of("run_id", "ns", "scenario_id", "controls", "allowed_tools")) {
            refused(() -> tokens.verify(signEd(KEYS, KEYS.kid(), b -> b.claim(claim, null)), RUN, "read_trade"));
        }
        refused(() -> tokens.verify(signEd(KEYS, KEYS.kid(), b -> b.claim("ns", "not-a-uuid")), RUN, "read_trade"));
        refused(() -> tokens.verify(signEd(KEYS, KEYS.kid(), b -> b.expirationTime(null)), RUN, "read_trade"));
        refused(() -> tokens.verify(signEd(KEYS, KEYS.kid(), b -> b.claim("controls", "everything")), RUN, "read_trade"));
    }

    @Test
    void OM_05_garbageIsRefusedNotThrown() {
        for (String junk : new String[] {null, "", "abc", "a.b.c", "a.b", "....", "Bearer x"}) {
            refused(() -> tokens.verify(junk, RUN, "read_trade"));
        }
    }

    @Test
    void OM_05_everyFailureIsTheSameError() {
        String good = tokens.issue(GRANT).token();
        List<GatewayException> all = new ArrayList<>();
        all.add(refused(() -> tokens.verify("abc", RUN, "read_trade")));
        all.add(refused(() -> tokens.verify(good, UUID.randomUUID(), "read_trade")));
        all.add(refused(() -> tokens.verify(good, RUN, "escalate_break")));
        all.add(refused(() -> tokens.verify(signEd(KEYS, KEYS.kid(), b -> b.audience("x")), RUN, "read_trade")));
        assertThat(all).extracting(GatewayException::detail).containsOnly(RunTokens.denied().detail());
        assertThat(all).allSatisfy(e -> assertThat(e.getMessage()).doesNotContain(good));
    }
}
