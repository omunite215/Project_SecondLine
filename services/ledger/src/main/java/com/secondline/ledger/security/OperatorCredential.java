package com.secondline.ledger.security;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/**
 * The /admin realm's bearer (OM-07): the harness operator. No default exists; unset or shorter than 32 characters
 * is a startup failure (make bootstrap generates 32 random bytes). Only a SHA-256 digest is kept, compared in
 * constant time, and toString never shows it.
 */
public final class OperatorCredential {
    private final byte[] digest;

    public OperatorCredential(String token) {
        if (token == null || token.isEmpty()) {
            throw new IllegalStateException("ledger.auth.operator-token (LEDGER_OPERATOR_TOKEN) is not set");
        }
        if (token.length() < 32) {
            throw new IllegalStateException("ledger.auth.operator-token (LEDGER_OPERATOR_TOKEN) must be at least 32 characters");
        }
        this.digest = sha256(token);
    }

    public boolean matches(String presented) {
        return presented != null && MessageDigest.isEqual(digest, sha256(presented));
    }

    private static byte[] sha256(String s) {
        try {
            return MessageDigest.getInstance("SHA-256").digest(s.getBytes(StandardCharsets.UTF_8));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }

    @Override
    public String toString() {
        return "OperatorCredential[redacted]";
    }
}
