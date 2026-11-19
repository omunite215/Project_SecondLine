package com.secondline.contracts;

import com.fasterxml.jackson.databind.JsonNode;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;

/** `sha256:<lowercase hex>`, the digest form every contract uses. */
public final class Digests {
    private Digests() {}

    public static String sha256(byte[] bytes) {
        try {
            return "sha256:" + HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 is mandatory on every JVM", e);
        }
    }

    /** sha256 over the UTF-8 bytes of the JCS form. */
    public static String sha256Canonical(JsonNode node) {
        return sha256(CanonicalJson.canonicalize(node).getBytes(StandardCharsets.UTF_8));
    }
}
