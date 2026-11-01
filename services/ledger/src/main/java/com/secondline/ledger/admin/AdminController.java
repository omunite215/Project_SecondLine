package com.secondline.ledger.admin;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.secondline.contracts.CanonicalJson;
import com.secondline.contracts.ContractException;
import com.secondline.contracts.Contracts;
import com.secondline.contracts.generated.ErrorCode;
import com.secondline.ledger.LedgerException;
import com.secondline.ledger.export.NamespaceExporter;
import com.secondline.ledger.export.StateHash;
import com.secondline.ledger.load.LoadResult;
import com.secondline.ledger.load.WorldBundleLoader;
import com.secondline.ledger.ns.NamespaceRepository;
import java.util.Set;
import java.util.UUID;
import java.util.regex.Pattern;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Harness-only namespace lifecycle (contracts openapi/ledger-admin.yaml, ADR-015, ADR-019): create → :load →
 * export / state-hash → retire, plus the agent_runs registry. Bodies are parsed strictly (duplicate keys and
 * trailing tokens rejected), so the bundle that is hashed is the bundle that was sent. Realm authentication
 * arrives with OM-07; until then the ledger listens on loopback only.
 */
@RestController
@RequestMapping("/admin/v1")
public class AdminController {
    private static final Set<String> RUN_KEYS = Set.of("ns", "controls", "agent_id", "manifest_ref");
    private static final Pattern OPAQUE = Pattern.compile("^[a-z]{2,6}_[0-9A-Za-z]{8,32}$");

    private final NamespaceRepository namespaces;
    private final WorldBundleLoader loader;
    private final NamespaceExporter exporter;
    private final JdbcClient jdbc;

    public AdminController(NamespaceRepository namespaces, WorldBundleLoader loader, NamespaceExporter exporter, JdbcClient jdbc) {
        this.namespaces = namespaces;
        this.loader = loader;
        this.exporter = exporter;
        this.jdbc = jdbc;
    }

    @PostMapping("/ns")
    public ResponseEntity<ObjectNode> create() {
        ObjectNode out = Contracts.MAPPER.createObjectNode().put("ns", namespaces.create().toString());
        return ResponseEntity.status(HttpStatus.CREATED).body(out);
    }

    @PostMapping("/ns/{ns}:load")
    public ResponseEntity<ObjectNode> load(@PathVariable UUID ns, @RequestBody String body) {
        LoadResult r = loader.load(ns, strict(body));
        return ResponseEntity.status(r.alreadyLoaded() ? HttpStatus.OK : HttpStatus.CREATED).body(hash(ns));
    }

    @GetMapping("/ns/{ns}/export")
    public ObjectNode export(@PathVariable UUID ns) {
        return exporter.export(ns);
    }

    @GetMapping("/ns/{ns}/state-hash")
    public ObjectNode stateHash(@PathVariable UUID ns) {
        return hash(ns);
    }

    @DeleteMapping("/ns/{ns}")
    public ResponseEntity<Void> retire(@PathVariable UUID ns) {
        namespaces.retire(ns);
        return ResponseEntity.noContent().build();
    }

    @PostMapping("/runs")
    public ResponseEntity<ObjectNode> registerRun(@RequestBody String body) {
        JsonNode req = strict(body);
        if (!req.isObject() || !RUN_KEYS.equals(keys(req)) || !RUN_KEYS.stream().allMatch(k -> req.get(k).isTextual())) {
            throw LedgerException.domainInvalid("run registration needs exactly the string fields " + new java.util.TreeSet<>(RUN_KEYS));
        }
        UUID ns;
        try {
            ns = UUID.fromString(req.get("ns").asText());
        } catch (IllegalArgumentException e) {
            throw LedgerException.domainInvalid("malformed parameter ns");
        }
        String controls = req.get("controls").asText();
        String agentId = req.get("agent_id").asText();
        if (!Set.of("off", "monitor", "full").contains(controls)) throw LedgerException.domainInvalid("malformed parameter controls");
        if (!OPAQUE.matcher(agentId).matches()) throw LedgerException.domainInvalid("malformed parameter agent_id");
        namespaces.requireLoaded(ns);
        UUID runId = UUID.randomUUID();
        com.secondline.ledger.journal.Db.domain(() -> jdbc.sql(
                        "INSERT INTO ledger.agent_runs (ns, run_id, controls, agent_id, manifest_ref) VALUES (?, ?, ?, ?, ?)")
                .params(ns, runId, controls, agentId, req.get("manifest_ref").asText()).update());
        ObjectNode out = Contracts.MAPPER.createObjectNode()
                .put("run_id", runId.toString()).put("ns", ns.toString()).put("controls", controls);
        return ResponseEntity.status(HttpStatus.CREATED).body(out);
    }

    private ObjectNode hash(UUID ns) {
        ObjectNode export = exporter.export(ns);
        return Contracts.MAPPER.createObjectNode()
                .put("ns", ns.toString())
                .put("snapshot_hash", export.get("snapshot_hash").asText())
                .put("state_hash", StateHash.of(export))
                .put("state_version", export.get("state_version").asLong());
    }

    private static JsonNode strict(String body) {
        try {
            return CanonicalJson.parse(body);
        } catch (ContractException e) {
            throw new LedgerException(ErrorCode.DOMAIN_INVALID, "body is not strict JSON");
        }
    }

    private static Set<String> keys(JsonNode n) {
        Set<String> keys = new java.util.HashSet<>();
        n.fieldNames().forEachRemaining(keys::add);
        return keys;
    }
}
