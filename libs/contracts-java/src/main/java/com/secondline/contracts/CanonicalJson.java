package com.secondline.contracts;

import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigInteger;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

/**
 * RFC 8785 (JCS) canonical form, restricted to integers. Contract numbers are only integers
 * (versions, state versions, seeds); money is a string (golden rule 3). Any other number, or an
 * integer outside ±(2^53−1), throws instead of taking JCS's ES6 float path.
 */
public final class CanonicalJson {
    private static final BigInteger MAX_SAFE = BigInteger.valueOf((1L << 53) - 1);
    private static final ObjectMapper STRICT = new ObjectMapper()
            .enable(JsonParser.Feature.STRICT_DUPLICATE_DETECTION)
            .enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS);

    private CanonicalJson() {}

    /** Parses strictly (no duplicate keys, no trailing tokens) and canonicalises. */
    public static String canonicalize(String json) {
        return canonicalize(parse(json));
    }

    public static String canonicalize(JsonNode node) {
        StringBuilder out = new StringBuilder();
        write(node, out);
        return out.toString();
    }

    public static JsonNode parse(String json) {
        try {
            return STRICT.readTree(json);
        } catch (JsonProcessingException e) {
            throw new ContractException("not I-JSON: " + e.getOriginalMessage(), e);
        }
    }

    private static void write(JsonNode node, StringBuilder out) {
        switch (node.getNodeType()) {
            case OBJECT -> {
                List<String> keys = new ArrayList<>();
                node.fieldNames().forEachRemaining(keys::add);
                keys.sort(null); // String.compareTo orders by UTF-16 code units, as RFC 8785 §3.2.3 requires
                out.append('{');
                for (int i = 0; i < keys.size(); i++) {
                    if (i > 0) out.append(',');
                    writeString(keys.get(i), out);
                    out.append(':');
                    write(node.get(keys.get(i)), out);
                }
                out.append('}');
            }
            case ARRAY -> {
                out.append('[');
                Iterator<JsonNode> it = node.elements();
                for (int i = 0; it.hasNext(); i++) {
                    if (i > 0) out.append(',');
                    write(it.next(), out);
                }
                out.append(']');
            }
            case STRING -> writeString(node.textValue(), out);
            case NUMBER -> {
                if (!node.isIntegralNumber()) {
                    throw new ContractException("non-integer number " + node + " (money and prices are strings)");
                }
                BigInteger n = node.bigIntegerValue();
                if (n.abs().compareTo(MAX_SAFE) > 0) {
                    throw new ContractException("integer " + n + " outside ±(2^53−1)");
                }
                out.append(n);
            }
            case BOOLEAN -> out.append(node.booleanValue());
            case NULL -> out.append("null");
            default -> throw new ContractException("unsupported JSON node " + node.getNodeType());
        }
    }

    private static void writeString(String s, StringBuilder out) {
        out.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"' -> out.append("\\\"");
                case '\\' -> out.append("\\\\");
                case '\b' -> out.append("\\b");
                case '\f' -> out.append("\\f");
                case '\n' -> out.append("\\n");
                case '\r' -> out.append("\\r");
                case '\t' -> out.append("\\t");
                default -> {
                    if (c < 0x20) {
                        out.append(String.format("\\u%04x", (int) c));
                    } else if (Character.isHighSurrogate(c) && i + 1 < s.length() && Character.isLowSurrogate(s.charAt(i + 1))) {
                        out.append(c).append(s.charAt(++i));
                    } else if (Character.isSurrogate(c)) {
                        // UTF-8 would encode it as '?', so two different strings would digest the same.
                        throw new ContractException("lone surrogate U+" + Integer.toHexString(c) + " is not I-JSON");
                    } else {
                        out.append(c);
                    }
                }
            }
        }
        out.append('"');
    }
}
