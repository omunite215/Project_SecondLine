package com.secondline.gateway.client;

/** OPA's answer (G9): decision ∈ ALLOW | DENY | REVIEW_REQUIRED, a reason, and the bundle that decided. */
public record PolicyDecision(String decision, String reason, String bundleHash) {}
