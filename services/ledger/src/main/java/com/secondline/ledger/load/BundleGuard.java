package com.secondline.ledger.load;

import com.fasterxml.jackson.databind.JsonNode;
import com.secondline.contracts.SchemaRegistry;
import com.secondline.ledger.LedgerException;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import org.springframework.stereotype.Component;

/**
 * The loader's gate (OM-04 §5, ADR-015, T-DOM-03): a WorldBundle that carries a truth key, a canary, breaks
 * its schema or points at something it doesn't contain is rejected with DOMAIN_INVALID before any write.
 * Messages name JSON pointers only, never values, so a rejection can't echo a canary or a cause.
 * Pure: no database access, so a rejection can't have written anything.
 */
@Component
public class BundleGuard {
    static final String SCHEMA = "scenario/world_bundle.schema.json";
    static final int MAX_DEPTH = 64;
    private static final String CANARY = "slcanary-";
    /** A B1–B8 root-cause label (common.schema.json break_type) is truth; it is never a visible value. */
    private static final java.util.regex.Pattern LABEL = java.util.regex.Pattern.compile("(?i)\\bB[1-8]_[A-Z]");

    private final SchemaRegistry schemas = SchemaRegistry.load();
    private final Set<String> truthKeys = TruthKeys.load();

    public void check(JsonNode bundle) {
        if (bundle == null || !bundle.isObject()) throw LedgerException.domainInvalid("bundle is not a JSON object");
        scan(bundle);
        List<String> errors = schemas.validate(SCHEMA, bundle);
        if (!errors.isEmpty()) {
            // networknt messages can quote the offending value; keep only the instance location.
            List<String> at = errors.stream().map(e -> e.substring(0, Math.max(0, e.indexOf(':')))).distinct().sorted().toList();
            throw LedgerException.domainInvalid("bundle fails " + SCHEMA + " at " + at);
        }
        new References(bundle).check();
    }

    /**
     * Truth keys (any case), canaries (in any key or string) and root-cause labels (in any string), anywhere in
     * the tree; iterative with a depth cap. A key is checked before it becomes part of a pointer, so no message
     * built from a pointer can carry a canary.
     */
    private void scan(JsonNode root) {
        record Node(JsonNode n, String ptr, int depth) {}
        Deque<Node> todo = new ArrayDeque<>();
        todo.push(new Node(root, "", 0));
        while (!todo.isEmpty()) {
            Node cur = todo.pop();
            if (cur.depth() > MAX_DEPTH) throw LedgerException.domainInvalid("bundle too deep at " + cur.ptr());
            JsonNode n = cur.n();
            if (n.isObject()) {
                for (Map.Entry<String, JsonNode> e : n.properties()) {
                    if (e.getKey().toLowerCase(Locale.ROOT).contains(CANARY)) {
                        throw LedgerException.domainInvalid("canary in a key under " + (cur.ptr().isEmpty() ? "/" : cur.ptr()));
                    }
                    String ptr = cur.ptr() + "/" + e.getKey();
                    if (truthKeys.contains(e.getKey().toLowerCase(Locale.ROOT))) {
                        throw LedgerException.domainInvalid("truth field in bundle at " + ptr);
                    }
                    todo.push(new Node(e.getValue(), ptr, cur.depth() + 1));
                }
            } else if (n.isArray()) {
                for (int i = 0; i < n.size(); i++) todo.push(new Node(n.get(i), cur.ptr() + "/" + i, cur.depth() + 1));
            } else if (n.isTextual()) {
                if (n.asText().toLowerCase(Locale.ROOT).contains(CANARY)) {
                    throw LedgerException.domainInvalid("canary in bundle at " + cur.ptr());
                }
                if (LABEL.matcher(n.asText()).find()) {
                    throw LedgerException.domainInvalid("root-cause label in bundle at " + cur.ptr());
                }
            }
        }
    }

    /** Cross-record consistency the schema can't express: every id resolves inside this bundle, once. */
    private static final class References {
        private final JsonNode b;
        private final Set<String> institutions;
        private final Set<String> counterparties;
        private final Set<String> isins;
        private final Set<String> trades;
        private final Set<String> evidence;
        private final Set<String> accounts;

        References(JsonNode b) {
            this.b = b;
            institutions = ids("institutions", "institution_id");
            counterparties = ids("counterparties", "counterparty_id");
            isins = ids("instruments", "isin");
            trades = ids("trades", "trade_id");
            accounts = ids("accounts", "account");
            ids("journal_entries", "entry_id");
            ids("securities_movements", "movement_id");
            ids("breaks", "break_id");
            ids("fx_rates", "rate_id");
            evidence = new HashSet<>();
            Set<String> versions = new HashSet<>();
            JsonNode ev = b.get("evidence");
            for (int i = 0; i < ev.size(); i++) {
                JsonNode f = ev.get(i).get("fields");
                if ("PARTIALLY_SETTLED".equals(f.path("status").asText()) && !f.has("quantity")) {
                    fail("/evidence/" + i + "/fields", "a partial settlement must state its quantity");
                }
                String id = ev.get(i).get("record_id").asText();
                if (!versions.add(id + "@" + ev.get(i).get("version").asText())) {
                    fail("/evidence/" + i, "duplicate record_id + version");
                }
                evidence.add(id);
            }
        }

        /**
         * The schema checks dates and timestamps by pattern only, so "2026-02-30" gets through it. Every key that
         * holds a date or a UTC instant, anywhere (evidence fields included), must parse on the calendar.
         */
        private static final Set<String> DATES = Set.of("as_of", "trade_date", "settlement_date", "effective_date",
                "settle_date", "value_date", "ex_date", "record_date", "pay_date");
        private static final Set<String> INSTANTS = Set.of("booked_at", "received_at", "opened_at", "retrieved_at",
                "cutoff_time");

        private void calendar(JsonNode n, String ptr) {
            if (n.isArray()) {
                for (int i = 0; i < n.size(); i++) calendar(n.get(i), ptr + "/" + i);
            } else if (n.isObject()) {
                for (Map.Entry<String, JsonNode> e : n.properties()) {
                    String p = ptr + "/" + e.getKey();
                    String v = e.getValue().isTextual() ? e.getValue().asText() : null;
                    try {
                        if (v != null && DATES.contains(e.getKey())) java.time.LocalDate.parse(v);
                        if (v != null && INSTANTS.contains(e.getKey())) java.time.OffsetDateTime.parse(v);
                    } catch (java.time.format.DateTimeParseException x) {
                        fail(p, "not a calendar date or UTC instant");
                    }
                    calendar(e.getValue(), p);
                }
            }
        }

        void check() {
            calendar(b, "");
            each("counterparties", (c, p) -> in(institutions, c, "institution_id", p));
            each("trades", (t, p) -> {
                in(counterparties, t, "counterparty_id", p);
                in(isins, t, "isin", p);
            });
            each("journal_entries", (e, p) -> {
                optional(trades, e, "trade_id", p);
                JsonNode lines = e.get("lines");
                for (int i = 0; i < lines.size(); i++) {
                    JsonNode l = lines.get(i);
                    String lp = p + "/lines/" + i;
                    in(accounts, l, "account", lp);
                    if (!l.get("account").asText().endsWith("-" + l.get("currency").asText())) {
                        fail(lp, "line currency differs from its account's currency");
                    }
                }
            });
            each("securities_movements", (m, p) -> {
                optional(trades, m, "trade_id", p);
                in(isins, m, "isin", p);
                in(accounts, m, "account", p);
                if (!m.get("account").asText().endsWith("-" + m.get("isin").asText())) {
                    fail(p, "movement isin differs from its account's isin");
                }
            });
            each("breaks", (k, p) -> {
                optional(isins, k, "isin", p);
                if (k.has("cash_difference") && k.has("currency")) {
                    int minor = com.secondline.ledger.domain.Currency.of(k.get("currency").asText()).minorUnits();
                    if (new java.math.BigDecimal(k.get("cash_difference").asText()).scale() > minor) {
                        fail(p + "/cash_difference", "finer than the currency's minor units");
                    }
                }
                all(trades, k, "trade_ids", p);
                all(evidence, k, "evidence_ids", p);
            });
        }

        private Set<String> ids(String array, String key) {
            Set<String> out = new HashSet<>();
            JsonNode a = b.get(array);
            for (int i = 0; i < a.size(); i++) {
                if (!out.add(a.get(i).get(key).asText())) fail("/" + array + "/" + i + "/" + key, "duplicate id");
            }
            return out;
        }

        private void each(String array, java.util.function.BiConsumer<JsonNode, String> f) {
            JsonNode a = b.get(array);
            for (int i = 0; i < a.size(); i++) f.accept(a.get(i), "/" + array + "/" + i);
        }

        private static void in(Set<String> known, JsonNode n, String key, String p) {
            if (!known.contains(n.get(key).asText())) fail(p + "/" + key, "unknown reference");
        }

        private static void optional(Set<String> known, JsonNode n, String key, String p) {
            if (n.has(key)) in(known, n, key, p);
        }

        private static void all(Set<String> known, JsonNode n, String key, String p) {
            JsonNode a = n.get(key);
            if (a == null) return;
            for (int i = 0; i < a.size(); i++) {
                if (!known.contains(a.get(i).asText())) fail(p + "/" + key + "/" + i, "unknown reference");
            }
        }

        private static void fail(String ptr, String why) {
            throw LedgerException.domainInvalid(why + " at " + ptr);
        }
    }
}
