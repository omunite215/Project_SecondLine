package com.secondline.gateway.route;

import java.util.List;

/**
 * One §10 tool's route. For READ, {@code pathTemplate} uses {ns} and the tool's own input field names, e.g.
 * "/internal/v1/ns/{ns}/trades/{trade_id}"; {@code queryParams} are optional input fields sent as query.
 */
public record ToolRoute(String tool, String risk, RouteKind kind, String pathTemplate, List<String> queryParams, String note) {
    public ToolRoute {
        queryParams = List.copyOf(queryParams);
    }
}
