package com.secondline.gateway.token;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.nio.file.attribute.PosixFilePermissions;
import java.security.GeneralSecurityException;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.Base64;
import java.util.HexFormat;

/**
 * Writes the gateway's Ed25519 signing key as a private JWK (OM-05 G4). JDK only, so `make bootstrap` runs it as a
 * single-file source program on both laptops: {@code java KeyGen.java secrets/gateway-signing.jwk}.
 * Never overwrites an existing key and never prints key material. File 0644 (the container's non-root user reads
 * the bind mount), directory 0700 (other host users can't reach it); secrets/ is git- and docker-ignored.
 */
public final class KeyGen {
    private KeyGen() {}

    public static void main(String[] args) throws IOException, GeneralSecurityException {
        if (args.length != 1) {
            System.err.println("usage: java KeyGen.java <path to private JWK>");
            System.exit(2);
        }
        Path out = Path.of(args[0]);
        if (Files.exists(out)) {
            System.out.println(out + ": exists, left unchanged");
            return;
        }
        Path dir = out.toAbsolutePath().getParent();
        Files.createDirectories(dir);
        Files.setPosixFilePermissions(dir, PosixFilePermissions.fromString("rwx------"));
        Files.writeString(out, jwk(KeyPairGenerator.getInstance("Ed25519").generateKeyPair()), StandardCharsets.UTF_8,
                StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
        Files.setPosixFilePermissions(out, PosixFilePermissions.fromString("rw-r--r--"));
        System.out.println(out + ": created (Ed25519 signing key)");
    }

    /** RFC 8037 OKP JWK. Raw keys are the last 32 bytes of the PKCS#8 / X.509 encodings (fixed RFC 8410 prefixes). */
    static String jwk(KeyPair kp) throws GeneralSecurityException {
        byte[] d = last32(kp.getPrivate().getEncoded());
        byte[] x = last32(kp.getPublic().getEncoded());
        String kid = "gw-" + HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(x)).substring(0, 16);
        Base64.Encoder b64 = Base64.getUrlEncoder().withoutPadding();
        String json = "{\"kty\":\"OKP\",\"crv\":\"Ed25519\",\"kid\":\"" + kid + "\",\"x\":\"" + b64.encodeToString(x)
                + "\",\"d\":\"" + b64.encodeToString(d) + "\"}\n";
        Arrays.fill(d, (byte) 0);
        return json;
    }

    private static byte[] last32(byte[] encoded) {
        return Arrays.copyOfRange(encoded, encoded.length - 32, encoded.length);
    }
}
