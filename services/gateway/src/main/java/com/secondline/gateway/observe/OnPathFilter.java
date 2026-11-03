package com.secondline.gateway.observe;

import com.secondline.gateway.route.ToolRoute;
import com.secondline.gateway.route.ToolRoutes;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.time.Duration;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * gateway.onpath (G13, MET-09, NFR-08): request received → response sent for every tool call, so it includes body
 * parsing, the pipeline and serialisation, and excludes the MCP hop (ADR-013). It is the H2 latency source: its
 * boundaries don't move without SH-06 sign-off. Tags: tool (a §10 name or "unknown", so random paths can't
 * explode cardinality) and the HTTP status.
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class OnPathFilter extends OncePerRequestFilter {
    static final Duration[] SLO = {Duration.ofMillis(1), Duration.ofMillis(2), Duration.ofMillis(5), Duration.ofMillis(10),
            Duration.ofMillis(20), Duration.ofMillis(50), Duration.ofMillis(100), Duration.ofMillis(200), Duration.ofMillis(500)};
    private static final Pattern TOOL_PATH = Pattern.compile("^/v1/runs/[^/]+/tools/([^/]+)$");
    private static final Set<String> TOOLS = ToolRoutes.all().stream().map(ToolRoute::tool).collect(Collectors.toUnmodifiableSet());

    private final MeterRegistry meters;

    public OnPathFilter(MeterRegistry meters) {
        this.meters = meters;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !TOOL_PATH.matcher(request.getRequestURI()).matches();
    }

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain)
            throws ServletException, IOException {
        long start = System.nanoTime();
        try {
            chain.doFilter(req, res);
        } finally {
            Matcher m = TOOL_PATH.matcher(req.getRequestURI());
            String tool = m.matches() && TOOLS.contains(m.group(1)) ? m.group(1) : "unknown";
            Timer.builder("gateway.onpath").description("tool call, request received to response sent (H2)")
                    .tag("tool", tool).tag("status", Integer.toString(res.getStatus()))
                    .publishPercentileHistogram().serviceLevelObjectives(SLO)
                    .register(meters).record(Duration.ofNanos(System.nanoTime() - start));
        }
    }
}
