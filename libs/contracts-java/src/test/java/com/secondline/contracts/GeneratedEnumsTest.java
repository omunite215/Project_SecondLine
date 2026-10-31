package com.secondline.contracts;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;

import com.fasterxml.jackson.databind.JsonNode;
import com.secondline.contracts.generated.ActionType;
import com.secondline.contracts.generated.Decision;
import com.secondline.contracts.generated.ErrorCode;
import com.secondline.contracts.generated.ReasonCode;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.OptionalInt;
import org.junit.jupiter.api.Test;

/** OM-02 §8 §9: generated enums equal their contract sources (make codegen-java). */
class GeneratedEnumsTest {
    static final Path ROOT = Path.of(System.getProperty("contracts.root"));

    static JsonNode read(String rel) throws IOException {
        return CanonicalJson.parse(Files.readString(ROOT.resolve(rel)));
    }

    static List<String> texts(JsonNode array) {
        List<String> out = new ArrayList<>();
        array.forEach(n -> out.add(n.asText()));
        return out;
    }

    static List<String> names(Enum<?>[] values) {
        return Arrays.stream(values).map(Enum::name).toList();
    }

    @Test
    void OM_02_error_code_enum_matches_errors_json() throws IOException {
        JsonNode errors = read("errors.json").path("errors");
        List<String> codes = new ArrayList<>();
        errors.forEach(e -> codes.add(e.path("code").asText()));
        assertEquals(codes, names(ErrorCode.values()));
        for (JsonNode e : errors) {
            ErrorCode c = ErrorCode.valueOf(e.path("code").asText());
            OptionalInt status = e.path("http_status").isNull()
                    ? OptionalInt.empty() : OptionalInt.of(e.path("http_status").asInt());
            assertEquals(status, c.httpStatus(), c.name());
            assertEquals(e.path("retryable").asBoolean(), c.retryable(), c.name());
            assertEquals(e.path("grader_only").asBoolean(), c.graderOnly(), c.name());
        }
    }

    @Test
    void OM_02_runtime_services_cannot_pick_a_grader_only_code() {
        // ORACLE_MISMATCH is grader-only (rules/contracts.md); runtime code uses runtimeValues().
        assertFalse(ErrorCode.runtimeValues().stream().anyMatch(ErrorCode::graderOnly));
        assertEquals(Arrays.stream(ErrorCode.values()).filter(c -> !c.graderOnly()).toList(), ErrorCode.runtimeValues());
    }

    @Test
    void OM_02_schema_enums_match() throws IOException {
        assertEquals(texts(read("common.schema.json").path("$defs").path("reason_code").path("enum")),
                names(ReasonCode.values()));
        assertEquals(texts(read("actions/proposed_action.schema.json").path("properties").path("type").path("enum")),
                names(ActionType.values()));
        assertEquals(texts(read("receipts/decision_receipt.schema.json").path("properties").path("decision").path("enum")),
                names(Decision.values()));
    }
}
