package com.secondline.contracts;

import com.fasterxml.jackson.databind.JsonNode;
import com.networknt.schema.Schema;
import com.networknt.schema.SchemaException;
import com.networknt.schema.SchemaLocation;
import com.networknt.schema.SpecificationVersion;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Validates documents against packages/contracts schemas (JSON Schema 2020-12), loaded from the
 * classpath copy under contracts/. `$id`s under {@link #ID_BASE} resolve to that copy and remote
 * fetching is off, so validation never touches the network. Schemas are compiled once and cached.
 */
public final class SchemaRegistry {
    public static final String ID_BASE = "https://secondline.invalid/contracts/1/";
    private static final String CLASSPATH_BASE = "contracts/";

    private final com.networknt.schema.SchemaRegistry registry;
    private final Map<String, Schema> cache = new ConcurrentHashMap<>();

    private SchemaRegistry(com.networknt.schema.SchemaRegistry registry) {
        this.registry = registry;
    }

    public static SchemaRegistry load() {
        return new SchemaRegistry(com.networknt.schema.SchemaRegistry.withDefaultDialect(
                SpecificationVersion.DRAFT_2020_12,
                b -> b.schemaLoader(l -> l.fetchRemoteResources(false)
                        .schemaIdResolvers(r -> r.mapPrefix(ID_BASE, "classpath:" + CLASSPATH_BASE)))));
    }

    /**
     * Errors for {@code doc} against {@code target} ("actions/proposed_action.schema.json", optionally
     * with a "#/$defs/x" fragment, as in an example's x-validates). Empty list means valid. An unknown or
     * unloadable schema throws {@link ContractException}: it is never reported as valid.
     */
    public List<String> validate(String target, JsonNode doc) {
        Schema schema = schema(target);
        try {
            return schema.validate(doc).stream()
                    .map(e -> e.getInstanceLocation() + ": " + e.getMessage())
                    .toList();
        } catch (SchemaException e) {
            throw new ContractException("cannot evaluate contract schema " + target, e);
        }
    }

    private Schema schema(String target) {
        return cache.computeIfAbsent(target, t -> {
            String file = t.contains("#") ? t.substring(0, t.indexOf('#')) : t;
            if (SchemaRegistry.class.getClassLoader().getResource(CLASSPATH_BASE + file) == null) {
                throw new ContractException("unknown contract schema: " + t);
            }
            try {
                Schema schema = registry.getSchema(SchemaLocation.of(ID_BASE + t));
                schema.initializeValidators(); // resolve every $ref now, so a broken schema is never cached
                return schema;
            } catch (RuntimeException e) {
                throw new ContractException("cannot load contract schema " + t, e);
            }
        });
    }
}
