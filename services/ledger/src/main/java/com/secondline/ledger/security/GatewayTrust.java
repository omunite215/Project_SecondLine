package com.secondline.ledger.security;

import com.nimbusds.jose.jwk.Curve;
import com.nimbusds.jose.jwk.JWK;
import com.nimbusds.jose.jwk.OctetKeyPair;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.text.ParseException;

/**
 * The one key the ledger trusts (OM-07): the PUBLIC half of the gateway's service-signing key, separate from the
 * run-token key, so no agent run token can ever verify here. Unset, unreadable, non-Ed25519, kid-less or private
 * key material is a startup failure: the ledger never runs unable to authenticate its caller (golden rule 7).
 */
public final class GatewayTrust {
    private final OctetKeyPair key;

    private GatewayTrust(OctetKeyPair key) {
        this.key = key;
    }

    public static GatewayTrust load(String path) {
        if (path == null || path.isBlank()) {
            throw new IllegalStateException("ledger.auth.gateway-jwk-path (LEDGER_GATEWAY_JWK_PATH) is not set");
        }
        JWK jwk;
        try {
            jwk = JWK.parse(Files.readString(Path.of(path)));
        } catch (IOException | ParseException e) {
            throw new IllegalStateException("cannot read the gateway service public key " + path, e);
        }
        if (!(jwk instanceof OctetKeyPair okp) || !Curve.Ed25519.equals(okp.getCurve())) {
            throw new IllegalStateException("the gateway service key must be an Ed25519 OKP JWK: " + path);
        }
        if (okp.isPrivate()) {
            throw new IllegalStateException("the gateway service key file holds a private key; mount only the public half: " + path);
        }
        if (okp.getKeyID() == null || okp.getKeyID().isBlank()) {
            throw new IllegalStateException("the gateway service key has no kid: " + path);
        }
        return new GatewayTrust(okp);
    }

    public String kid() {
        return key.getKeyID();
    }

    OctetKeyPair publicJwk() {
        return key;
    }
}
