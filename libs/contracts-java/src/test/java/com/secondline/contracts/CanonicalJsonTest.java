package com.secondline.contracts;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.api.Test;

/** OM-02 §9 ADR-011: RFC 8785 (JCS), restricted to integers (golden rule 3: amounts are strings). */
class CanonicalJsonTest {

    @Test
    void OM_02_jcs_sorts_keys_by_utf16_code_units() {
        // RFC 8785 §3.2.3 sorting example: U+1F600 (surrogates D83D DE00) sorts before U+FB33.
        String in = "{\"\\u20ac\":\"Euro Sign\",\"\\r\":\"Carriage Return\",\"\\ufb33\":\"Hebrew Letter Dalet With Dagesh\","
                + "\"1\":\"One\",\"\\ud83d\\ude00\":\"Emoji: Grinning Face\",\"\\u0080\":\"Control\","
                + "\"\\u00f6\":\"Latin Small Letter O With Diaeresis\"}";
        String expected = "{\"\\r\":\"Carriage Return\",\"1\":\"One\",\"\u0080\":\"Control\","
                + "\"\u00f6\":\"Latin Small Letter O With Diaeresis\",\"\u20ac\":\"Euro Sign\","
                + "\"\ud83d\ude00\":\"Emoji: Grinning Face\",\"\ufb33\":\"Hebrew Letter Dalet With Dagesh\"}";
        assertEquals(expected, CanonicalJson.canonicalize(in));
    }

    @Test
    void OM_02_jcs_escapes_only_what_rfc8785_requires() {
        String in = "{\"s\":\"q\\\" b\\\\ / \\b\\f\\n\\r\\t \\u0001 \\u001f \\u007f é\"}";
        String expected = "{\"s\":\"q\\\" b\\\\ / \\b\\f\\n\\r\\t \\u0001 \\u001f \u007f é\"}";
        assertEquals(expected, CanonicalJson.canonicalize(in));
    }

    @Test
    void OM_02_jcs_drops_whitespace_and_keeps_array_order() {
        assertEquals("{\"a\":[3,1,2],\"b\":{\"x\":null,\"y\":true,\"z\":false}}",
                CanonicalJson.canonicalize(" { \"b\" : {\"z\":false, \"y\":true ,\"x\":null}, \"a\":[ 3, 1, 2 ] } "));
    }

    @Test
    void OM_02_jcs_integers_print_plainly() {
        assertEquals("[0,0,-1,9007199254740991,-9007199254740991]",
                CanonicalJson.canonicalize("[0,-0,-1,9007199254740991,-9007199254740991]"));
    }

    @Test
    void OM_02_jcs_rejects_fraction_exponent_and_unsafe_int() {
        for (String bad : new String[] {"1.5", "1.0", "1e2", "[9007199254740992]", "{\"a\":-9007199254740992}"}) {
            assertThrows(ContractException.class, () -> CanonicalJson.canonicalize(bad), bad);
        }
    }

    @Test
    void OM_02_jcs_rejects_lone_surrogate() {
        // UTF-8 encoding would turn each into '?', so distinct documents would digest the same.
        for (String bad : new String[] {"\"\\ud800\"", "\"\\udc00x\"", "{\"\\ud83d\":1}", "\"a\\ude00\\ud83d\""}) {
            assertThrows(ContractException.class, () -> CanonicalJson.canonicalize(bad), bad);
        }
    }

    @Test
    void OM_02_jcs_rejects_duplicate_keys() {
        assertThrows(ContractException.class, () -> CanonicalJson.canonicalize("{\"a\":1,\"a\":2}"));
    }

    @Test
    void OM_02_jcs_is_idempotent() {
        String once = CanonicalJson.canonicalize("{\"b\":[{\"d\":1,\"c\":\"\\u00e9\"}],\"a\":\"x\"}");
        assertEquals(once, CanonicalJson.canonicalize(once));
    }
}
