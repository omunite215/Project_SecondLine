package com.secondline.ledger.security;

import java.time.Clock;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnWebApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.access.intercept.AuthorizationFilter;
import org.springframework.security.web.firewall.RequestRejectedHandler;

/**
 * OM-07 §11 SEC-02: one filter chain per realm, default deny. /internal/** gateway service JWT (aud=ledger, ns from
 * the token = ns in the path); /admin/** operator credential (+ the gateway's register_run); /review/** closed until
 * OM-20; only health is open. Stateless bearer auth: no sessions, cookies, CSRF tokens, Basic or form login.
 * Not loaded by the one-shot migrator (no web server, profile `migrate`).
 */
@Configuration
@EnableWebSecurity
@ConditionalOnWebApplication(type = ConditionalOnWebApplication.Type.SERVLET)
public class LedgerSecurityConfig {

    @Bean
    GatewayTrust gatewayTrust(@Value("${ledger.auth.gateway-jwk-path:}") String path) {
        return GatewayTrust.load(path);
    }

    @Bean
    OperatorCredential operatorCredential(@Value("${ledger.auth.operator-token:}") String token) {
        return new OperatorCredential(token);
    }

    @Bean
    ServiceTokenVerifier serviceTokenVerifier(GatewayTrust trust) {
        return new ServiceTokenVerifier(trust, Clock.systemUTC());
    }

    @Bean
    @Order(1)
    SecurityFilterChain internalRealm(HttpSecurity http, ServiceTokenVerifier verifier, OperatorCredential op) throws Exception {
        return stateless(http.securityMatcher("/internal/**"), new RealmFilter(RealmFilter.Realm.INTERNAL, verifier, op))
                .authorizeHttpRequests(a -> a.anyRequest().hasRole(RealmFilter.ROLE_GATEWAY)).build();
    }

    @Bean
    @Order(2)
    SecurityFilterChain adminRealm(HttpSecurity http, ServiceTokenVerifier verifier, OperatorCredential op) throws Exception {
        return stateless(http.securityMatcher("/admin/**"), new RealmFilter(RealmFilter.Realm.ADMIN, verifier, op))
                .authorizeHttpRequests(a -> a
                        .requestMatchers(HttpMethod.POST, "/admin/v1/runs").hasAnyRole(RealmFilter.ROLE_OPERATOR, RealmFilter.ROLE_GATEWAY)
                        .anyRequest().hasRole(RealmFilter.ROLE_OPERATOR))
                .build();
    }

    @Bean
    @Order(3)
    SecurityFilterChain health(HttpSecurity http) throws Exception {
        return stateless(http.securityMatcher("/actuator/health", "/actuator/health/**"), null)
                .authorizeHttpRequests(a -> a.anyRequest().permitAll()).build();
    }

    /** /review/** (OM-20 adds the human realm) and every unlisted path. */
    @Bean
    @Order(4)
    SecurityFilterChain everythingElse(HttpSecurity http) throws Exception {
        return stateless(http.securityMatcher("/**"), null).authorizeHttpRequests(a -> a.anyRequest().denyAll()).build();
    }

    /** A request line the firewall rejects (dot segments, encoded slashes) gets the same contract 403, not a bare 400. */
    @Bean
    RequestRejectedHandler requestRejectedHandler() {
        return (req, res, e) -> Deny.write(res);
    }

    private static HttpSecurity stateless(HttpSecurity http, RealmFilter filter) throws Exception {
        http.csrf(AbstractHttpConfigurer::disable)
                .httpBasic(AbstractHttpConfigurer::disable)
                .formLogin(AbstractHttpConfigurer::disable)
                .logout(AbstractHttpConfigurer::disable)
                .requestCache(AbstractHttpConfigurer::disable)
                .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .exceptionHandling(x -> x.authenticationEntryPoint((req, res, e) -> Deny.write(res))
                        .accessDeniedHandler((req, res, e) -> Deny.write(res)));
        if (filter != null) http.addFilterBefore(filter, AuthorizationFilter.class);
        return http;
    }
}
