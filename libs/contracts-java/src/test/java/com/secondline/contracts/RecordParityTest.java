package com.secondline.contracts;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.secondline.contracts.generated.ErrorCode;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;
import org.junit.jupiter.api.Test;

/** OM-02 §9: hand-written records stay equal to their schemas (the generator check for records). */
class RecordParityTest {
    static final Path ROOT = Path.of(System.getProperty("contracts.root"));

    static JsonNode read(String rel) throws IOException {
        return CanonicalJson.parse(Files.readString(ROOT.resolve(rel)));
    }

    static Set<String> jsonNames(Class<? extends Record> type) {
        Set<String> out = new TreeSet<>();
        for (var c : type.getRecordComponents()) {
            JsonProperty p = c.getAccessor().getAnnotation(JsonProperty.class); // not RECORD_COMPONENT-targeted
            out.add(p != null ? p.value() : c.getName());
        }
        return out;
    }

    static Set<String> properties(JsonNode schema) {
        Set<String> out = new TreeSet<>();
        schema.path("properties").fieldNames().forEachRemaining(out::add);
        return out;
    }

    @Test
    void OM_02_records_match_schema_properties() throws IOException {
        assertEquals(properties(read("actions/proposed_action.schema.json")), jsonNames(ProposedAction.class));
        assertEquals(properties(read("common.schema.json").path("$defs").path("evidence_ref")), jsonNames(EvidenceRef.class));
        assertEquals(properties(read("error_response.schema.json")), jsonNames(ErrorResponse.class));
    }

    @Test
    void OM_02_error_response_codes_are_the_runtime_codes() throws IOException {
        List<String> schema = new ArrayList<>();
        read("error_response.schema.json").path("properties").path("error_code").path("enum")
                .forEach(n -> schema.add(n.asText()));
        assertEquals(schema, ErrorCode.runtimeValues().stream().map(Enum::name).toList());
    }

    @Test
    void OM_02_every_action_example_round_trips() throws IOException {
        for (String name : List.of("proposed_action_adjustment", "proposed_action_classify", "proposed_action_escalate")) {
            ObjectNode doc = (ObjectNode) read("examples/actions/" + name + ".json");
            doc.remove("x-validates");
            ProposedAction action = Contracts.MAPPER.treeToValue(doc, ProposedAction.class);
            assertEquals(CanonicalJson.canonicalize(doc), CanonicalJson.canonicalize(Contracts.MAPPER.valueToTree(action)), name);
            assertEquals(ActionDigest.of(doc), action.actionDigest(), name);
        }
    }

    @Test
    void OM_02_error_response_example_round_trips() throws IOException {
        ObjectNode doc = (ObjectNode) read("examples/error_response_state_conflict.json");
        doc.remove("x-validates");
        assertEquals(CanonicalJson.canonicalize(doc), CanonicalJson.canonicalize(
                Contracts.MAPPER.valueToTree(Contracts.MAPPER.treeToValue(doc, ErrorResponse.class))));
    }

    @Test
    void OM_02_error_response_rejects_grader_only_code() {
        assertThrows(ContractException.class, () -> new ErrorResponse(
                ErrorCode.ORACLE_MISMATCH, "x", "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d", null));
        assertThrows(IOException.class, () -> Contracts.MAPPER.readValue(
                "{\"error_code\":\"ORACLE_MISMATCH\",\"message\":\"x\",\"request_id\":\"0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d\"}",
                ErrorResponse.class));
    }

    @Test
    void OM_02_error_response_requires_code_message_and_request_id() {
        assertThrows(ContractException.class, () -> new ErrorResponse(null, "x", "r", null));
        assertThrows(ContractException.class, () -> new ErrorResponse(ErrorCode.STATE_CONFLICT, null, "r", null));
        assertThrows(ContractException.class, () -> new ErrorResponse(ErrorCode.STATE_CONFLICT, "x", null, null));
    }

    @Test
    void OM_02_mapper_never_coerces_scalars() {
        for (String bad : new String[] {
                "{\"record_id\":\"ev_00000017\",\"version\":3.7}",
                "{\"record_id\":\"ev_00000017\",\"version\":3.0}",
                "{\"record_id\":\"ev_00000017\",\"version\":\"3\"}",
                "{\"record_id\":12.5,\"version\":3}",
                "{\"record_id\":true,\"version\":3}"}) {
            assertThrows(IOException.class, () -> Contracts.MAPPER.readValue(bad, EvidenceRef.class), bad);
        }
    }

    @Test
    void OM_02_unknown_field_rejected_on_read() {
        assertThrows(IOException.class, () -> Contracts.MAPPER.readValue(
                "{\"record_id\":\"ev_00000017\",\"version\":2,\"x\":1}", EvidenceRef.class));
    }
}
