package com.secondline.gateway;

import com.secondline.gateway.token.SigningKeys;
import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;

/** A throwaway signing key on disk for Spring contexts (the real one comes from make bootstrap, G4). */
public final class TestKeys {
    private static Path file;
    private static Path serviceFile;

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

    /** OM-07: the separate service-signing key (gateway → ledger JWTs). */
    public static synchronized String servicePath() {
        if (serviceFile == null) {
            try {
                serviceFile = Files.createTempFile("gateway-service", ".jwk");
                Files.writeString(serviceFile, SigningKeys.generate("gw-svc-test-v1").privateJwk().toJSONString());
                serviceFile.toFile().deleteOnExit();
            } catch (IOException e) {
                throw new UncheckedIOException(e);
            }
        }
        return serviceFile.toString();
    }
}
