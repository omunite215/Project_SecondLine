package com.secondline.ledger;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpStatus;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

/** OM-01 §7: the skeleton boots and exposes only readiness/liveness health, nothing else from actuator. */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class LedgerApplicationTest {

    @Autowired
    TestRestTemplate http;

    // OM-03: the app now has a datasource; it connects as ledger_svc like in compose (ADR-019).
    @DynamicPropertySource
    static void db(DynamicPropertyRegistry r) {
        LedgerDb.migrate();
        r.add("spring.datasource.url", LedgerDb::jdbcUrl);
        r.add("spring.datasource.username", () -> "ledger_svc");
        r.add("spring.datasource.password", () -> LedgerDb.APP_PW);
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
