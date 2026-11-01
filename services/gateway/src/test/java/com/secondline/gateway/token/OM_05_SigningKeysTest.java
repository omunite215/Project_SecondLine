package com.secondline.gateway.token;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** OM-05 G4: the key `make bootstrap` writes loads; anything else stops the gateway at startup. */
class OM_05_SigningKeysTest {
    @TempDir Path dir;

    @Test
    void OM_05_keygenOutputLoads() throws Exception {
        Path f = dir.resolve("s/gateway-signing.jwk");
        KeyGen.main(new String[] {f.toString()});
        SigningKeys k = SigningKeys.load(f);
        assertThat(k.kid()).matches("^gw-[0-9a-f]{16}$");
        assertThat(k.publicJwk().isPrivate()).isFalse();
        assertThat(k.toString()).doesNotContain(k.privateJwk().getD().toString());
    }

    @Test
    void OM_05_missingOrBadKeyStopsStartup() throws Exception {
        assertThatThrownBy(() -> SigningKeys.load(dir.resolve("nope.jwk"))).isInstanceOf(IllegalStateException.class);
        Path pub = dir.resolve("pub.jwk");
        Files.writeString(pub, SigningKeys.generate("gw-0000000000000002").publicJwk().toJSONString());
        assertThatThrownBy(() -> SigningKeys.load(pub)).isInstanceOf(IllegalStateException.class).hasMessageContaining("private");
        Path junk = dir.resolve("junk.jwk");
        Files.writeString(junk, "{}");
        assertThatThrownBy(() -> SigningKeys.load(junk)).isInstanceOf(IllegalStateException.class);
    }
}
