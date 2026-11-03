package com.secondline.gateway;

import com.secondline.gateway.token.SigningKeys;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;

/** A throwaway signing key on disk for Spring contexts (the real one comes from make bootstrap, G4). */
public final class TestKeys {
    private static Path file;

    private TestKeys() {}

    public static synchronized String path() {
        if (file == null) {
            try {
                file = Files.createTempFile("gateway-signing", ".jwk");
                Files.writeString(file, SigningKeys.generate("gw-test-v1").privateJwk().toJSONString());
                file.toFile().deleteOnExit();
            } catch (IOException e) {
                throw new UncheckedIOException(e);
            }
        }
        return file.toString();
    }
}
