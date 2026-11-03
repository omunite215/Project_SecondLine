package com.secondline.gateway;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpStatus;

/** OM-01 §7: the skeleton boots and exposes only readiness/liveness health, nothing else from actuator. */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class GatewayApplicationTest {

    @Autowired
    TestRestTemplate http;

    // OM-05: the gateway won't start without its signing key (G4); dependencies point nowhere on purpose.
    @org.springframework.test.context.DynamicPropertySource
    static void config(org.springframework.test.context.DynamicPropertyRegistry r) {
        r.add("gateway.signing-jwk-path", TestKeys::path);
        r.add("gateway.ledger-url", () -> "http://127.0.0.1:1");
        r.add("gateway.opa-url", () -> "http://127.0.0.1:1");
    }

    @Test
    void OM01_readinessIsUp() {
        var r = http.getForEntity("/actuator/health/readiness", String.class);
        assertThat(r.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(r.getBody()).isEqualTo("{\"status\":\"UP\"}");
    }

    @Test
    void OM01_onlyHealthExposed() {
        for (String path : new String[] {"/actuator/env", "/actuator/beans", "/actuator/configprops"}) {
            assertThat(http.getForEntity(path, String.class).getStatusCode()).as(path).isEqualTo(HttpStatus.NOT_FOUND);
        }
    }

    @Test
    void OM01_healthHidesDetails() {
        assertThat(http.getForEntity("/actuator/health", String.class).getBody()).doesNotContain("components");
    }
}
