package com.secondline.ledger.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.Collections;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * Authenticates one realm's caller from the single Bearer credential, or leaves the request anonymous (then the
 * chain's rule denies it). INTERNAL: a gateway service JWT whose ns claim equals the {ns} path segment. ADMIN: the
 * operator credential, or the gateway's service JWT on POST /admin/v1/runs only, where the controller re-checks
 * that the body's ns is the token's (request attribute {@link #TOKEN_NS}).
 */
final class RealmFilter extends OncePerRequestFilter {
    enum Realm { INTERNAL, ADMIN }

    static final String TOKEN_NS = com.secondline.ledger.admin.AdminController.TOKEN_NS;
    static final String ROLE_GATEWAY = "GATEWAY";
    static final String ROLE_OPERATOR = "OPERATOR";
    private static final Pattern INTERNAL_NS = Pattern.compile("^/internal/v1/ns/([^/]+)(?:/.*)?$");

    private final Realm realm;
    private final ServiceTokenVerifier verifier;
    private final OperatorCredential operator;

    RealmFilter(Realm realm, ServiceTokenVerifier verifier, OperatorCredential operator) {
        this.realm = realm;
        this.verifier = verifier;
        this.operator = operator;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain)
            throws ServletException, IOException {
        String bearer = bearer(req);
        if (bearer != null) {
            switch (realm) {
                case INTERNAL -> verifier.verify(bearer).filter(ns -> ns.toString().equals(pathNs(req)))
                        .ifPresent(ns -> authenticate(req, ROLE_GATEWAY, ns));
                case ADMIN -> {
                    if (operator.matches(bearer)) {
                        authenticate(req, ROLE_OPERATOR, null);
                    } else if ("POST".equals(req.getMethod()) && "/admin/v1/runs".equals(req.getServletPath())) {
                        verifier.verify(bearer).ifPresent(ns -> authenticate(req, ROLE_GATEWAY, ns));
                    }
                }
            }
        }
        chain.doFilter(req, res);
    }

    /** Exactly one Authorization header, scheme Bearer, a credential without whitespace; anything else is none. */
    static String bearer(HttpServletRequest req) {
        List<String> values = Collections.list(req.getHeaders("Authorization"));
        if (values.size() != 1) return null;
        String v = values.get(0);
        if (v.length() < 8 || !v.regionMatches(true, 0, "Bearer ", 0, 7)) return null;
        String token = v.substring(7);
        return token.isEmpty() || token.chars().anyMatch(Character::isWhitespace) ? null : token;
    }

    private static String pathNs(HttpServletRequest req) {
        Matcher m = INTERNAL_NS.matcher(req.getServletPath());
        return m.matches() ? m.group(1) : null;
    }

    private static void authenticate(HttpServletRequest req, String role, UUID ns) {
        var auth = UsernamePasswordAuthenticationToken.authenticated(role.toLowerCase(), null,
                List.of(new SimpleGrantedAuthority("ROLE_" + role)));
        SecurityContext ctx = SecurityContextHolder.createEmptyContext();
        ctx.setAuthentication(auth);
        SecurityContextHolder.setContext(ctx);
        Optional.ofNullable(ns).ifPresent(n -> req.setAttribute(TOKEN_NS, n));
    }
}
