package com.secondline.ledger.export;

import static com.secondline.ledger.Bundles.minimal;
import static com.secondline.ledger.Bundles.with;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.secondline.contracts.CanonicalJson;
import com.secondline.contracts.Contracts;
import com.secondline.contracts.generated.ErrorCode;
import com.secondline.ledger.LedgerDb;
import com.secondline.ledger.LedgerException;
import com.secondline.ledger.Services;
import java.io.IOException;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.UUID;
import net.jqwik.api.ForAll;
import net.jqwik.api.Property;
import net.jqwik.api.constraints.LongRange;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** OM-04 §12 T-EVAL-03 ADR-015 Amendment 1: load → export → hash is the same on every load and machine. */
class T_EVAL_03_StateHashTest {
    static final NamespaceExporter EXPORTER = Services.exporter();

    @BeforeAll
    static void schema() {
        LedgerDb.migrate();
    }

    static JsonNode contracts(String rel) {
        try {
            return Contracts.MAPPER.readTree(Path.of(System.getProperty("contracts.root"), rel).toFile());
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    static ObjectNode loaded(ObjectNode bundle) {
        LedgerDb.migrate();  // jqwik properties don't run JUnit's @BeforeAll; migrate() is idempotent
        UUID ns = Services.namespaces().create();
        Services.loader().load(ns, bundle);
        return EXPORTER.export(ns);
    }

    @Test
    void T_EVAL_03_twoLoadsSameHash() {
        ObjectNode a = loaded(minimal());
        ObjectNode b = loaded(minimal());
        assertThat(a.get("ns")).isNotEqualTo(b.get("ns"));
        assertThat(StateHash.of(a)).isEqualTo(StateHash.of(b));
    }

    @Test
    void T_EVAL_03_minimalBundleMatchesGoldenVector() {
        // The vector was computed by Python's json (tests/kit/test_om_04_state_hash.py), not by this code.
        JsonNode v = contracts("test-vectors/state_hash/minimal.json");
        ObjectNode export = loaded(minimal());
        assertThat(export.get("snapshot_hash").asText()).isEqualTo(v.get("snapshot_hash").asText());
        ObjectNode withoutNs = export.deepCopy();
        withoutNs.remove("ns");
        // Compare canonical forms: Jackson's LongNode(0) and a parsed IntNode(0) are the same JSON.
        assertThat(CanonicalJson.canonicalize(withoutNs)).isEqualTo(CanonicalJson.canonicalize(v.get("export_without_ns")));
        assertThat(StateHash.of(export)).isEqualTo(v.get("state_hash").asText());
    }

    @Test
    void T_EVAL_03_exportValidatesAndCarriesNs() {
        ObjectNode export = loaded(minimal());
        assertThat(com.secondline.contracts.SchemaRegistry.load().validate("scenario/ns_export.schema.json", export)).isEmpty();
        assertThat(export.get("ns").asText()).isNotBlank();
        assertThat(export.get("state_version").asLong()).isZero();
    }

    @Test
    void OM_04_hashChangesWithState() {
        ObjectNode a = loaded(minimal());
        ObjectNode moved = loaded(with(b -> {
            ((ObjectNode) b.at("/journal_entries/0/lines/0")).put("amount", "3703.67");
            ((ObjectNode) b.at("/journal_entries/0/lines/1")).put("amount", "3703.67");
        }));
        assertThat(StateHash.of(a)).isNotEqualTo(StateHash.of(moved));
    }

    @Test
    void OM_04_exportOfUnknownOrRetiredNamespaceDenied() {
        Throwable t = catchThrowable(() -> EXPORTER.export(UUID.randomUUID()));
        assertThat(t).isInstanceOf(LedgerException.class);
        assertThat(((LedgerException) t).code()).isEqualTo(ErrorCode.PERMISSION_DENIED);
    }

    @Property(tries = 5)
    void T_EVAL_03_hashIndependentOfBundleArrayOrder(@ForAll @LongRange(min = 1, max = 1_000_000) long seed) {
        // Shuffling every array changes the bundle's own hash (snapshot) but not the state it describes.
        ObjectNode shuffled = minimal();
        for (String key : List.of("evidence", "securities_movements", "accounts")) {
            List<JsonNode> items = new ArrayList<>();
            shuffled.get(key).forEach(items::add);
            Collections.shuffle(items, new java.util.Random(seed));
            ArrayNode arr = shuffled.putArray(key);
            items.forEach(arr::add);
        }
        ObjectNode a = loaded(minimal());
        ObjectNode b = loaded(shuffled);
        ObjectNode aBalances = a.deepCopy();
        ObjectNode bBalances = b.deepCopy();
        aBalances.remove(List.of("ns", "snapshot_hash"));
        bBalances.remove(List.of("ns", "snapshot_hash"));
        assertThat(CanonicalJson.canonicalize(bBalances)).isEqualTo(CanonicalJson.canonicalize(aBalances));
    }
}
