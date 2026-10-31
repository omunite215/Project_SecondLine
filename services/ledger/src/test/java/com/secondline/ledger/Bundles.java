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
}
