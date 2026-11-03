package com.secondline.gateway.client;

import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CopyOnWriteArrayList;

/** A tiny JDK HTTP stub (no extra dependency): records every request, answers with a fixed reply. */
final class StubServer implements AutoCloseable {
    record Seen(String method, String path, String query, Map<String, List<String>> headers, String body) {}

    record Reply(int status, String body, long delayMillis) {}

    private final HttpServer server;
    final List<Seen> seen = new CopyOnWriteArrayList<>();
    volatile Reply reply = new Reply(200, "{}", 0);

    StubServer() throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/", ex -> {
            String body = new String(ex.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
            seen.add(new Seen(ex.getRequestMethod(), ex.getRequestURI().getRawPath(), ex.getRequestURI().getRawQuery(),
                    ex.getRequestHeaders(), body));
            Reply r = reply;
            try {
                Thread.sleep(r.delayMillis());
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            byte[] out = r.body().getBytes(StandardCharsets.UTF_8);
            ex.getResponseHeaders().add("Content-Type", "application/json");
            ex.sendResponseHeaders(r.status(), out.length == 0 ? -1 : out.length);
            if (out.length > 0) ex.getResponseBody().write(out);
            ex.close();
        });
        server.start();
    }

    String url() {
        return "http://127.0.0.1:" + server.getAddress().getPort();
    }

    @Override
    public void close() {
        server.stop(0);
    }
}
