package com.secondline.gateway.token;

import com.nimbusds.jose.JOSEException;
import com.nimbusds.jose.jwk.Curve;
import com.nimbusds.jose.jwk.OctetKeyPair;
import com.nimbusds.jose.jwk.gen.OctetKeyPairGenerator;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.text.ParseException;

/**
 * The gateway's Ed25519 signing key (G4), loaded once from the private JWK `make bootstrap` writes (KeyGen).
 * A missing, unreadable, public-only or non-Ed25519 key is a startup failure: the gateway never runs unable to
 * sign or verify. {@link #toString()} never prints key material.
 */
public final class SigningKeys {
    private final OctetKeyPair privateJwk;

    private SigningKeys(OctetKeyPair privateJwk) {
        this.privateJwk = privateJwk;
    }

    public static SigningKeys load(Path file) {
        try {
            OctetKeyPair jwk = OctetKeyPair.parse(Files.readString(file));
            if (!Curve.Ed25519.equals(jwk.getCurve())) throw new IllegalStateException("signing key is not Ed25519: " + file);
            if (!jwk.isPrivate()) throw new IllegalStateException("signing key has no private part: " + file);
            if (jwk.getKeyID() == null || jwk.getKeyID().isBlank()) throw new IllegalStateException("signing key has no kid: " + file);
            return new SigningKeys(jwk);
        } catch (IOException e) {
            throw new IllegalStateException("cannot read signing key " + file, e);
        } catch (ParseException e) {
            throw new IllegalStateException("signing key is not a JWK: " + file, e);
        }
    }

    /** A fresh in-memory key (tests). */
    public static SigningKeys generate(String kid) {
        try {
            return new SigningKeys(new OctetKeyPairGenerator(Curve.Ed25519).keyID(kid).generate());
        } catch (JOSEException e) {
            throw new IllegalStateException(e);
        }
    }

    public OctetKeyPair privateJwk() {
        return privateJwk;
    }

    public OctetKeyPair publicJwk() {
        return privateJwk.toPublicJWK();
    }

    public String kid() {
        return privateJwk.getKeyID();
    }

    @Override
    public String toString() {
        return "SigningKeys[kid=" + kid() + "]";
    }
}
