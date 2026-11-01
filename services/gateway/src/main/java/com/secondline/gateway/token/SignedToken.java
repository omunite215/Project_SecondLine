package com.secondline.gateway.token;

import java.time.Instant;

/** A compact JWS run token and its expiry (contracts runs/run_token.schema.json: token + expires_at). */
public record SignedToken(String token, Instant expiresAt) {}
