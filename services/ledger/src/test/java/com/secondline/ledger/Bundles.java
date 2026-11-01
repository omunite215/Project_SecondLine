package com.secondline.ledger;

import com.fasterxml.jackson.databind.node.ObjectNode;
import com.secondline.contracts.Contracts;
import java.io.IOException;
import java.nio.file.Path;
import java.util.function.Consumer;

/** WorldBundle fixtures: the contracts example (packages/contracts, the file the Python kit checks too). */
public final class Bundles {
    private Bundles() {}

    public static ObjectNode minimal() {
        try {
            ObjectNode b = (ObjectNode) Contracts.MAPPER.readTree(
                    Path.of(System.getProperty("contracts.root"), "examples/scenario/world_bundle_minimal.json").toFile());
            b.remove("x-validates");
            return b;
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    /** The minimal bundle with one edit applied. */
    public static ObjectNode with(Consumer<ObjectNode> edit) {
        ObjectNode b = minimal();
        edit.accept(b);
        return b;
    }

    /** Minimal plus one record of every kind the read tools serve: custodian, CA notice, SSI and an FX rate. */
    public static ObjectNode rich() {
        return with(b -> {
            var ev = b.withArray("evidence");
            ev.addObject().put("record_id", "evd_0000E004").put("version", 1).put("kind", "CUSTODIAN_STATEMENT")
                    .put("source_system", "custody_sim").put("received_at", "2026-03-02T16:00:00Z").put("text", "Holdings.")
                    .putObject("fields").put("isin", "XS0000000012").put("quantity", "300").put("as_of", "2026-03-02");
            ev.addObject().put("record_id", "evd_0000E005").put("version", 1).put("kind", "CA_NOTICE")
                    .put("source_system", "ca_feed").put("received_at", "2026-03-02T16:00:00Z").put("text", "2-for-1 split.")
                    .putObject("fields").put("isin", "XS0000000012").put("event_type", "SPLF").put("ratio_new", "2")
                    .put("ratio_old", "1").put("ex_date", "2026-03-10");
            ev.addObject().put("record_id", "ssi_0000E006").put("version", 1).put("kind", "SSI_RECORD")
                    .put("source_system", "ssi_store").put("received_at", "2026-03-01T09:00:00Z").put("text", "Standing instruction.")
                    .putObject("fields").put("counterparty", "cpt_0000H001").put("currency", "USD").put("effective_date", "2026-01-01");
            b.withArray("fx_rates").addObject().put("rate_id", "fxr_0000F001").put("base", "EUR").put("quote", "USD")
                    .put("rate", "1.0850").put("source", "ecb").put("as_of", "2026-03-02");
        });
    }
}
