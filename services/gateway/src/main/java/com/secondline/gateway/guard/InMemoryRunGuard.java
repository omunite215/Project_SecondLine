package com.secondline.gateway.guard;

import com.secondline.contracts.generated.ErrorCode;
import com.secondline.gateway.GatewayException;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.IntSupplier;

/** Harness-safety caps per run (G10); forgotten on restart, which is the documented OM-05 limit. */
public class InMemoryRunGuard implements RunGuard {
    private final int maxCalls;
    private final ConcurrentHashMap<UUID, AtomicInteger> calls = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<UUID, AtomicInteger> messages = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<UUID, Integer> messageBudgets = new ConcurrentHashMap<>();
    private final Set<UUID> halted = ConcurrentHashMap.newKeySet();

    public InMemoryRunGuard(int maxCalls) {
        this.maxCalls = maxCalls;
    }

    @Override
    public void admit(UUID runId) {
        if (calls.computeIfAbsent(runId, k -> new AtomicInteger()).incrementAndGet() > maxCalls) {
            throw new GatewayException(ErrorCode.RUN_HALTED, "run over its call budget");
        }
    }

    @Override
    public boolean halted(UUID runId) {
        return halted.contains(runId);
    }

    @Override
    public void halt(UUID runId) {
        halted.add(runId);
    }

    @Override
    public boolean tryConsumeMessage(UUID runId, IntSupplier budget) {
        int limit = messageBudgets.computeIfAbsent(runId, k -> budget.getAsInt()); // a failing lookup is not cached
        return messages.computeIfAbsent(runId, k -> new AtomicInteger()).incrementAndGet() <= limit;
    }
}
