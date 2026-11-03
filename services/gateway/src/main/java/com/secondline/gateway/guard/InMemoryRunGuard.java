package com.secondline.gateway.guard;

import com.secondline.contracts.generated.ErrorCode;
import com.secondline.gateway.GatewayException;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

/** Harness-safety caps per run (G10); forgotten on restart, which is the documented OM-05 limit. */
public class InMemoryRunGuard implements RunGuard {
    private final int maxCalls;
    private final int maxMessages;
    private final ConcurrentHashMap<UUID, AtomicInteger> calls = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<UUID, AtomicInteger> messages = new ConcurrentHashMap<>();
    private final Set<UUID> halted = ConcurrentHashMap.newKeySet();

    public InMemoryRunGuard(int maxCalls, int maxMessages) {
        this.maxCalls = maxCalls;
        this.maxMessages = maxMessages;
    }

    @Override
    public void admit(UUID runId) {
        if (halted.contains(runId) || calls.computeIfAbsent(runId, k -> new AtomicInteger()).incrementAndGet() > maxCalls) {
            throw new GatewayException(ErrorCode.RUN_HALTED, "run halted or over its call budget");
        }
    }

    @Override
    public boolean tryConsumeMessage(UUID runId) {
        return messages.computeIfAbsent(runId, k -> new AtomicInteger()).incrementAndGet() <= maxMessages;
    }

    @Override
    public void halt(UUID runId) {
        halted.add(runId);
    }
}
