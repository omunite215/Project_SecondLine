package com.secondline.ledger.export;

import com.fasterxml.jackson.databind.node.ObjectNode;
import com.secondline.contracts.Digests;

/**
 * State hash = sha256(JCS(ns export without "ns")) (ADR-015 Amendment 1, T-EVAL-03). The ns UUID differs on
 * every load, so it names the run, not the state; everything else in the export is state.
 */
public final class StateHash {
    private StateHash() {}

    public static String of(ObjectNode export) {
        return Digests.sha256Canonical(export.deepCopy().without("ns"));
    }
}
