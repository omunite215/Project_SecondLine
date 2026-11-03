package com.secondline.gateway.client;

import com.fasterxml.jackson.databind.JsonNode;
import com.secondline.contracts.CanonicalJson;
import com.secondline.contracts.ContractException;
import com.secondline.contracts.generated.ErrorCode;
import com.secondline.gateway.GatewayException;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

/** One JDK HttpClient call with a hard timeout. Anything but a parsable JSON answer is RETRYABLE_UNAVAILABLE. */
final class Http {
    private static final HttpClient CLIENT = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2))
            .version(HttpClient.Version.HTTP_1_1).build();

    record Answer(int status, JsonNode body) {}

    private Http() {}

    static Answer send(HttpRequest.Builder req, Duration timeout, String what) {
        HttpResponse<String> r;
        try {
            r = CLIENT.send(req.timeout(timeout).build(), HttpResponse.BodyHandlers.ofString());
        } catch (IOException e) {
            throw unavailable(what, e);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw unavailable(what, e);
        }
        if (r.statusCode() >= 500) throw unavailable(what, null);
        try {
            return new Answer(r.statusCode(), CanonicalJson.parse(r.body()));
        } catch (ContractException e) {
            throw unavailable(what, e);
        }
    }

    static URI uri(String base, String pathAndQuery) {
        return URI.create(base + pathAndQuery);
    }

    static GatewayException unavailable(String what, Throwable cause) {
        return new GatewayException(ErrorCode.RETRYABLE_UNAVAILABLE, what + " unavailable", cause);
    }
}
