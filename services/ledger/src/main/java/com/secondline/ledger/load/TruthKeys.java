package com.secondline.ledger.load;

import com.fasterxml.jackson.databind.JsonNode;
import com.secondline.contracts.Contracts;
import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;

/**
 * Key names that exist only in hidden truth (ADR-015, T-DOM-03), lower-cased: every property name in
 * scenario/truth.schema.json that the visible WorldBundle schema doesn't also use, plus truth_ref, canary and
 * explanation (rules/truth-isolation.md lists it; truth.schema.json doesn't have it yet).
 * Shared names (break_id, isin, currency, …) are visible by design, so "any truth-schema name" would reject
 * every bundle. Derived from the contracts on the classpath, never hand-copied, so it follows schema changes.
 */
public final class TruthKeys {
    private TruthKeys() {}

    public static Set<String> load() {
        Set<String> keys = propertyNames("contracts/scenario/truth.schema.json");
        keys.removeAll(propertyNames("contracts/scenario/world_bundle.schema.json"));
        keys.add("truth_ref");
        keys.add("canary");
        keys.add("explanation");
        return Set.copyOf(keys);
    }

    private static Set<String> propertyNames(String resource) {
        JsonNode schema;
        try (InputStream in = TruthKeys.class.getClassLoader().getResourceAsStream(resource)) {
            if (in == null) throw new IllegalStateException("contract schema missing from classpath: " + resource);
            schema = Contracts.MAPPER.readTree(in);
        } catch (IOException e) {
            throw new IllegalStateException("cannot read " + resource, e);
        }
        Set<String> out = new HashSet<>();
        Deque<JsonNode> todo = new ArrayDeque<>();
        todo.push(schema);
        while (!todo.isEmpty()) {
            JsonNode n = todo.pop();
            if (n.isObject()) {
                n.properties().forEach(e -> {
                    if (e.getKey().equals("properties") && e.getValue().isObject()) {
                        e.getValue().fieldNames().forEachRemaining(k -> out.add(k.toLowerCase(Locale.ROOT)));
                    }
                    todo.push(e.getValue());
                });
            } else if (n.isArray()) {
                n.forEach(todo::push);
            }
        }
        return out;
    }
}
