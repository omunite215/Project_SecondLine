package com.secondline.ledger;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.autoconfigure.security.servlet.UserDetailsServiceAutoConfiguration;

/** Financial authority: the only component that mutates financial state (ADR-002). Skeleton (OM-01). */
// OM-07: no generated default user/password; callers authenticate only through the realm filters.
@SpringBootApplication(exclude = UserDetailsServiceAutoConfiguration.class)
public class LedgerApplication {

    public static void main(String[] args) {
        SpringApplication.run(LedgerApplication.class, args);
    }
}
