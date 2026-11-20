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

    @Test
    void OM_07_keygenWritesThePublicHalfForTheLedger() throws Exception {
        Path f = dir.resolve("s/gateway-service.jwk");
        KeyGen.main(new String[] {f.toString()});
        Path pub = dir.resolve("s/gateway-service.pub.jwk");
        var jwk = com.nimbusds.jose.jwk.OctetKeyPair.parse(Files.readString(pub));
        assertThat(jwk.isPrivate()).isFalse();
        assertThat(Files.readString(pub)).doesNotContain("\"d\"");
        assertThat(jwk.getKeyID()).isEqualTo(SigningKeys.load(f).kid());
        assertThat(jwk.getX()).isEqualTo(SigningKeys.load(f).publicJwk().getX());
        // A key from before OM-07: the public file is derived on the next bootstrap, the private one left unchanged.
        Files.delete(pub);
        String before = Files.readString(f);
        KeyGen.main(new String[] {f.toString()});
        assertThat(Files.readString(f)).isEqualTo(before);
        assertThat(com.nimbusds.jose.jwk.OctetKeyPair.parse(Files.readString(pub)).isPrivate()).isFalse();
        // Rotation: a new private key never keeps the old public file.
        Files.delete(f);
        KeyGen.main(new String[] {f.toString()});
        assertThat(com.nimbusds.jose.jwk.OctetKeyPair.parse(Files.readString(pub)).getX()).isEqualTo(SigningKeys.load(f).publicJwk().getX());
        // Nimbus orders members differently ("d" not last): still stripped.
        assertThat(KeyGen.publicOnly(SigningKeys.generate("gw-0000000000000003").privateJwk().toJSONString())).doesNotContain("\"d\"");
    }
}
