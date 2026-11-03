package com.secondline.gateway.guard;

import java.util.UUID;
import java.util.function.IntSupplier;

/**
 * G10 harness safety. ADR-014: budgets/time caps are on in every condition; the supervisor's kill switch (halt) is
 * off in condition B, so the pipeline applies {@link #halted} only in monitor/full. OM-12 replaces this in-memory
 * version with ledger-backed flags.
 */
public interface RunGuard {
    /** Count one verified tool call; RUN_HALTED once the run is over its call budget. */
    void admit(UUID runId);

    boolean halted(UUID runId);

    void halt(UUID runId);

    /**
     * Spend one simulated counterparty message. The run's budget C_msg is looked up once with {@code budget}
     * (ADR-014 placeholder: the number of breaks in the run); false when it is used up.
     */
    boolean tryConsumeMessage(UUID runId, IntSupplier budget);
}
