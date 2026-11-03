package com.secondline.gateway.guard;

import java.util.UUID;

/** G10 budget/halt check, in every control condition (ADR-014). OM-12 replaces the in-memory one. */
public interface RunGuard {
    /** Count one tool call; RUN_HALTED if the run is halted or over its call budget. */
    void admit(UUID runId);

    /** Spend one simulated message (C_msg); false when the budget is gone (the pipeline answers POLICY_DENIED). */
    boolean tryConsumeMessage(UUID runId);

    void halt(UUID runId);
}
