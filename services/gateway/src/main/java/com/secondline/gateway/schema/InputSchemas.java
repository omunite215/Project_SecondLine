package com.secondline.gateway.schema;

import com.fasterxml.jackson.databind.JsonNode;
import com.secondline.contracts.SchemaRegistry;
import com.secondline.contracts.generated.ErrorCode;
import com.secondline.gateway.GatewayException;
import com.secondline.gateway.route.ToolRoutes;
import java.util.List;

/**
 * Checks a tool's input against tools/<tool>.input.schema.json before anything is routed. The error names the
 * tool and how many rules failed, never the input (it may carry injected text or canaries).
 */
public class InputSchemas {
    private final SchemaRegistry registry;

    public InputSchemas(SchemaRegistry registry) {
        this.registry = registry;
    }

    public void validate(String tool, JsonNode input) {
        ToolRoutes.of(tool); // unknown tool → PERMISSION_DENIED before any schema lookup
        List<String> errors = registry.validate("tools/" + tool + ".input.schema.json", input);
        if (!errors.isEmpty()) {
            throw new GatewayException(ErrorCode.DOMAIN_INVALID,
                    "input does not match the " + tool + " schema (" + errors.size() + " violation" + (errors.size() == 1 ? "" : "s") + ")");
        }
    }
}
