package com.secondline.gateway.pipeline;

/** Where a decision was made; the values of decision_log_entry.stage (G8). */
public enum Stage {
    TOKEN("token"), BINDING("binding"), SCHEMA("schema"), GUARD("guard"), POLICY("policy"), LEDGER("ledger"), ROUTED("routed");

    private final String wire;

    Stage(String wire) {
        this.wire = wire;
    }

    public String wire() {
        return wire;
    }
}
