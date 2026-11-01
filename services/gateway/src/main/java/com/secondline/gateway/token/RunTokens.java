package com.secondline.gateway.token;

import com.secondline.contracts.generated.ErrorCode;
import com.secondline.gateway.GatewayException;
import java.time.Clock;
import java.time.Duration;
import java.util.UUID;

/**
 * Issues and verifies run tokens (OM-05 G2 G3, §11 identity scheme, ADR-013, ADR-015).
 *
 * <p><b>[Om writes]</b> {@link #issue} and {@link #verify}. The spec is {@code OM_05_RunTokensTest}; the rules:
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

    private final SigningKeys keys;
    private final Clock clock;
    private final Duration ttl;

    public RunTokens(SigningKeys keys, Clock clock, Duration ttl) {
        this.keys = keys;
        this.clock = clock;
        this.ttl = ttl;
    }

    public SignedToken issue(RunGrant grant) {
        throw new UnsupportedOperationException("[Om writes] OM-05 Task 2");
    }

    public RunClaims verify(String token, UUID pathRunId, String tool) {
        throw new UnsupportedOperationException("[Om writes] OM-05 Task 2");
    }

    /** The only error verify() may throw. */
    public static GatewayException denied() {
        return new GatewayException(ErrorCode.PERMISSION_DENIED, "run token not accepted for this run and tool");
    }
}
