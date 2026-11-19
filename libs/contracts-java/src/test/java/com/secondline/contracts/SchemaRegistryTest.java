package com.secondline.contracts;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;

/**
 * OM-02 §9 REQ-005: the Java validator agrees with scripts/contracts_check.py on every example
 * (examples/** valid, examples/invalid/** rejected), using the same x-validates targets.
 */
class SchemaRegistryTest {
    static final Path ROOT = Path.of(System.getProperty("contracts.root"));
    static final SchemaRegistry REGISTRY = SchemaRegistry.load();

    record Example(String rel, String target, JsonNode doc) {}

    static List<Example> examples(boolean invalid) throws IOException {
        List<Example> out = new ArrayList<>();
        try (Stream<Path> files = Files.walk(ROOT.resolve("examples"))) {
            for (Path f : files.filter(p -> p.toString().endsWith(".json")).sorted().toList()) {
                String rel = ROOT.relativize(f).toString().replace('\\', '/');
                if (rel.startsWith("examples/invalid/") != invalid) continue;
                ObjectNode doc = (ObjectNode) CanonicalJson.parse(Files.readString(f));
                out.add(new Example(rel, doc.remove("x-validates").asText(), doc));
            }
        }
        return out;
    }

    @Test
    void OM_02_every_example_validates() throws IOException {
        List<Example> all = examples(false);
        assertTrue(all.size() >= 30, "examples found: " + all.size());
        List<String> failures = new ArrayList<>();
        for (Example e : all) {
            List<String> errors = REGISTRY.validate(e.target(), e.doc());
            if (!errors.isEmpty()) failures.add(e.rel() + ": " + errors);
        }
        assertEquals(List.of(), failures);
    }

    @Test
    void OM_02_every_invalid_example_rejected() throws IOException {
        List<Example> all = examples(true);
        assertTrue(all.size() >= 30, "invalid examples found: " + all.size());
        List<String> accepted = new ArrayList<>();
        for (Example e : all) {
            if (REGISTRY.validate(e.target(), e.doc()).isEmpty()) accepted.add(e.rel());
        }
        assertEquals(List.of(), accepted);
    }

    @Test
    void OM_02_unknown_schema_fails_closed() {
        assertThrows(ContractException.class,
                () -> REGISTRY.validate("actions/no_such.schema.json", CanonicalJson.parse("{}")));
    }

    @Test
    void OM_02_missing_fragment_fails_closed() {
        assertThrows(ContractException.class,
                () -> REGISTRY.validate("common.schema.json#/$defs/no_such_def", CanonicalJson.parse("\"x\"")));
    }

    @Test
    void OM_02_dangling_ref_fails_closed_with_contract_exception() {
        assertThrows(ContractException.class,
                () -> REGISTRY.validate("testonly/dangling_ref.schema.json", CanonicalJson.parse("{}")));
    }

    @Test
    void OM_02_remote_ref_is_never_fetched_and_fails_closed() {
        assertThrows(ContractException.class,
                () -> REGISTRY.validate("testonly/remote_ref.schema.json", CanonicalJson.parse("{}")));
    }

    @Test
    void OM_02_errors_json_validates_against_its_schema() throws IOException {
        ObjectNode doc = (ObjectNode) CanonicalJson.parse(Files.readString(ROOT.resolve("errors.json")));
        String target = doc.remove("x-validates").asText();
        assertEquals(List.of(), REGISTRY.validate(target, doc));
    }

    @Test
    void OM_02_validation_reports_the_failing_path() throws IOException {
        ObjectNode doc = (ObjectNode) CanonicalJson.parse(
                Files.readString(ROOT.resolve("examples/actions/proposed_action_adjustment.json")));
        doc.remove("x-validates");
        doc.put("expected_state_version", -1);
        List<String> errors = REGISTRY.validate("actions/proposed_action.schema.json", doc);
        assertFalse(errors.isEmpty());
        assertTrue(errors.toString().contains("expected_state_version"), errors.toString());
    }
}
