package com.secondline.ledger.read;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.secondline.contracts.CanonicalJson;
import com.secondline.contracts.Contracts;
import com.secondline.contracts.Digests;
import com.secondline.contracts.generated.ErrorCode;
import com.secondline.ledger.LedgerException;
import com.secondline.ledger.domain.Currency;
import com.secondline.ledger.ns.NamespaceRepository;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.charset.StandardCharsets;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.function.Function;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * The §10 read tools over one namespace (OM-04, REQ-001 REQ-002, ADR-015 ADR-017). Each call runs in one
 * read-only REPEATABLE READ snapshot and returns exactly the tool's output shape. An id that doesn't resolve
 * in this ns (or a ns that isn't LOADED) is PERMISSION_DENIED, the same answer in every case.
 * Evidence-backed reads use the latest version of each evidence record, and return its version, so what the
 * agent reads is what it cites.
 */
@Service
public class ReadService {
    private static final DateTimeFormatter UTC = DateTimeFormatter.ISO_INSTANT;
    /** Latest version of each evidence record of one kind in ns. */
    private static final String LATEST = """
            SELECT DISTINCT ON (id) id, version, fields::text, observed_at FROM ledger.evidence_records
            WHERE ns = ? AND kind = ? ORDER BY id, version DESC""";

    private final JdbcClient jdbc;
    private final NamespaceRepository namespaces;
    private final TransactionTemplate snapshot;

    public ReadService(JdbcClient jdbc, NamespaceRepository namespaces, TransactionTemplate tx) {
        this.jdbc = jdbc;
        this.namespaces = namespaces;
        this.snapshot = new TransactionTemplate(tx.getTransactionManager());
        this.snapshot.setReadOnly(true);
        this.snapshot.setIsolationLevel(TransactionTemplate.ISOLATION_REPEATABLE_READ);
    }

    private <T> T read(UUID ns, Function<NamespaceRepository.Row, T> work) {
        return snapshot.execute(s -> work.apply(namespaces.requireLoaded(ns)));
    }

    static LedgerException denied() {
        return new LedgerException(ErrorCode.PERMISSION_DENIED, "not available in this namespace");
    }

    /** as_of_version: absent → current; outside 0..current → DOMAIN_INVALID (never clamped). */
    static long asOf(NamespaceRepository.Row row, Long asOf) {
        if (asOf == null) return row.stateVersion();
        if (asOf < 0 || asOf > row.stateVersion()) throw LedgerException.domainInvalid("as_of_version outside 0.." + row.stateVersion());
        return asOf;
    }

    // ---- breaks ---------------------------------------------------------------------------------------------

    public ObjectNode listBreaks(UUID ns, String status) {
        String st = status == null ? null : Params.breakStatus(status);
        return read(ns, row -> {
            ObjectNode out = obj();
            ArrayNode arr = out.putArray("breaks");
            jdbc.sql(BREAK + " AND (?::text IS NULL OR status = ?) ORDER BY id").params(ns, st, st)
                    .query((rs, i) -> breakNode(rs)).list().forEach(arr::add);
            return out;
        });
    }

    public ObjectNode getBreak(UUID ns, String breakId) {
        String id = Params.id("break_id", breakId);
        return read(ns, row -> {
            ObjectNode out = obj();
            out.set("break", jdbc.sql(BREAK + " AND id = ?").params(ns, id).query((rs, i) -> breakNode(rs)).optional()
                    .orElseThrow(ReadService::denied));
            ArrayNode trades = out.putArray("trade_ids");
            jdbc.sql("SELECT trade_id FROM ledger.break_trades WHERE ns = ? AND break_id = ? ORDER BY trade_id")
                    .params(ns, id).query(String.class).list().forEach(trades::add);
            ArrayNode ev = out.putArray("evidence_ids");
            jdbc.sql("SELECT record_id FROM ledger.break_evidence WHERE ns = ? AND break_id = ? ORDER BY record_id")
                    .params(ns, id).query(String.class).list().forEach(ev::add);
            out.put("opened_at", utc(jdbc.sql("SELECT opened_at FROM ledger.breaks WHERE ns = ? AND id = ?").params(ns, id)
                    .query(OffsetDateTime.class).single()));
            return out;
        });
    }

    private static final String BREAK = """
            SELECT id, status, symptom, currency, isin, coalesce(cash_difference, quantity_difference),
                   record_version, state_version FROM ledger.breaks WHERE ns = ?""";

    private static ObjectNode breakNode(ResultSet rs) throws SQLException {
        ObjectNode b = obj();
        b.put("break_id", rs.getString(1));
        b.put("status", rs.getString(2));
        b.put("symptom", rs.getString(3));
        putIfPresent(b, "currency", rs.getString(4));
        putIfPresent(b, "isin", rs.getString(5));
        BigDecimal diff = rs.getBigDecimal(6);
        if (diff != null) b.put("difference", diff.toPlainString());
        b.put("record_version", rs.getInt(7));
        b.put("state_version", rs.getLong(8));
        return b;
    }

    // ---- trades and bookings --------------------------------------------------------------------------------

    /** Trades are loaded at version 0 and never edited in v1 (corrections are journal reversals). */
    public ObjectNode readTrade(UUID ns, String tradeId, Long asOfVersion) {
        String id = Params.id("trade_id", tradeId);
        return read(ns, row -> {
            asOf(row, asOfVersion);
            return jdbc.sql("""
                            SELECT t.id, i.isin, t.side, t.quantity, t.price, t.currency, t.trade_date, t.settlement_date,
                                   t.counterparty_id, t.record_version
                            FROM ledger.trades t JOIN ledger.instruments i ON i.ns = t.ns AND i.id = t.instrument_id
                            WHERE t.ns = ? AND t.id = ?""")
                    .params(ns, id)
                    .query((rs, i) -> {
                        ObjectNode t = obj();
                        t.put("trade_id", rs.getString(1));
                        t.put("isin", rs.getString(2));
                        t.put("side", rs.getString(3));
                        t.put("quantity", rs.getBigDecimal(4).toPlainString());
                        t.put("price", rs.getBigDecimal(5).toPlainString());
                        t.put("currency", rs.getString(6));
                        t.put("trade_date", rs.getString(7));
                        t.put("settlement_date", rs.getString(8));
                        t.put("counterparty_id", rs.getString(9));
                        t.put("record_version", rs.getInt(10));
                        return t;
                    })
                    .optional().orElseThrow(ReadService::denied);
        });
    }

    /** Cash entries booked against a trade, as of a version (securities movements aren't agent-readable in v1). */
    public ObjectNode readBookings(UUID ns, String tradeId, Long asOfVersion) {
        String id = Params.id("trade_id", tradeId);
        return read(ns, row -> {
            long v = asOf(row, asOfVersion);
            requireTrade(ns, id);
            ObjectNode out = obj();
            ArrayNode entries = out.putArray("entries");
            record H(UUID entryId, String ref, String type, String date, String reverses) {}
            List<H> headers = jdbc.sql("""
                            SELECT h.entry_id, h.ref, h.entry_type, h.business_date, r.ref
                            FROM ledger.journal_headers h
                            LEFT JOIN ledger.journal_headers r ON r.ns = h.ns AND r.entry_id = h.reverses_entry_id
                            WHERE h.ns = ? AND h.trade_id = ? AND h.committed_version <= ?
                            ORDER BY h.committed_version, h.posted_at, h.ref""")
                    .params(ns, id, v)
                    .query((rs, i) -> new H(rs.getObject(1, UUID.class), rs.getString(2), rs.getString(3), rs.getString(4),
                            rs.getString(5)))
                    .list();
            for (H h : headers) {
                ObjectNode e = entries.addObject();
                e.put("entry_id", h.ref());
                e.put("entry_type", h.type());
                e.put("effective_date", h.date());
                putIfPresent(e, "reverses_entry_id", h.reverses());
                ArrayNode lines = e.putArray("lines");
                jdbc.sql("SELECT account_code, currency, amount, side FROM ledger.journal_lines WHERE ns = ? AND entry_id = ?"
                                + " ORDER BY line_no")
                        .params(ns, h.entryId())
                        .query((rs, i) -> {
                            ObjectNode l = obj();
                            l.put("account", rs.getString(1) + "-" + rs.getString(2));
                            l.put("currency", rs.getString(2));
                            l.put("amount", rs.getBigDecimal(3).toPlainString());
                            l.put("side", "D".equals(rs.getString(4)) ? "DEBIT" : "CREDIT");
                            return l;
                        })
                        .list().forEach(lines::add);
                e.put("record_version", 1);  // committed entries are immutable (T-DOM-05)
            }
            return out;
        });
    }

    private void requireTrade(UUID ns, String tradeId) {
        if (jdbc.sql("SELECT 1 FROM ledger.trades WHERE ns = ? AND id = ?").params(ns, tradeId).query(Integer.class).optional()
                .isEmpty()) {
            throw denied();
        }
    }

    // ---- positions ------------------------------------------------------------------------------------------

    /**
     * Positions as of a version, recomputed from the securities ledger (trading = S100 + S200, settled = S100),
     * and cost = Σ(1300 debits − credits) over cash entries whose trade is in that ISIN. Cash entries with no
     * trade (none in v1 bundles) aren't attributed to any ISIN.
     */
    public ObjectNode readPositions(UUID ns, String isinFilter, Long asOfVersion) {
        String isin = isinFilter == null ? null : Params.isin("isin", isinFilter);
        return read(ns, row -> {
            long v = asOf(row, asOfVersion);
            ObjectNode out = obj();
            ArrayNode arr = out.putArray("positions");
            jdbc.sql("""
                            SELECT i.isin, i.currency,
                              coalesce((SELECT sum(CASE l.side WHEN 'D' THEN l.quantity ELSE -l.quantity END)
                                        FROM ledger.securities_lines l JOIN ledger.securities_entries e
                                          ON e.ns = l.ns AND e.entry_id = l.entry_id
                                        WHERE l.ns = i.ns AND l.isin = i.isin AND l.account_code IN ('S100', 'S200')
                                          AND e.committed_version <= ?), 0),
                              coalesce((SELECT sum(CASE l.side WHEN 'D' THEN l.quantity ELSE -l.quantity END)
                                        FROM ledger.securities_lines l JOIN ledger.securities_entries e
                                          ON e.ns = l.ns AND e.entry_id = l.entry_id
                                        WHERE l.ns = i.ns AND l.isin = i.isin AND l.account_code = 'S100'
                                          AND e.committed_version <= ?), 0),
                              coalesce((SELECT sum(CASE l.side WHEN 'D' THEN l.amount ELSE -l.amount END)
                                        FROM ledger.journal_lines l
                                        JOIN ledger.journal_headers h ON h.ns = l.ns AND h.entry_id = l.entry_id
                                        JOIN ledger.trades t ON t.ns = h.ns AND t.id = h.trade_id
                                        WHERE l.ns = i.ns AND t.instrument_id = i.id AND l.account_code = '1300'
                                          AND h.committed_version <= ?), 0)
                            FROM ledger.instruments i
                            WHERE i.ns = ? AND (?::text IS NULL OR i.isin = ?) ORDER BY i.isin""")
                    .params(v, v, v, ns, isin, isin)
                    .query((rs, i) -> {
                        ObjectNode p = obj();
                        Currency ccy = Currency.of(rs.getString(2));
                        p.put("isin", rs.getString(1));
                        p.put("trading_position", rs.getBigDecimal(3).setScale(0, RoundingMode.UNNECESSARY).toPlainString());
                        p.put("settled_position", rs.getBigDecimal(4).setScale(0, RoundingMode.UNNECESSARY).toPlainString());
                        p.put("cost", rs.getBigDecimal(5).setScale(ccy.minorUnits(), RoundingMode.UNNECESSARY).toPlainString());
                        p.put("currency", ccy.name());
                        return p;
                    })
                    .list().forEach(arr::add);
            out.put("state_version", v);
            return out;
        });
    }

    // ---- evidence-backed reads (ADR-017) --------------------------------------------------------------------

    record Ev(String id, int version, JsonNode fields, OffsetDateTime observedAt) {}

    private List<Ev> latest(UUID ns, String kind) {
        return jdbc.sql(LATEST).params(ns, kind)
                .query((rs, i) -> new Ev(rs.getString(1), rs.getInt(2), parse(rs.getString(3)), rs.getObject(4, OffsetDateTime.class)))
                .list();
    }

    /** The most recently received SETTLEMENT_STATUS record naming this trade. */
    public ObjectNode readSettlementStatus(UUID ns, String tradeId) {
        String id = Params.id("trade_id", tradeId);
        return read(ns, row -> {
            requireTrade(ns, id);
            Ev ev = latest(ns, "SETTLEMENT_STATUS").stream()
                    .filter(e -> id.equals(e.fields().path("trade_ref").asText(null)) && e.fields().has("status"))
                    .max(java.util.Comparator.comparing(Ev::observedAt).thenComparing(Ev::id))
                    .orElseThrow(ReadService::denied);
            ObjectNode out = obj();
            out.put("trade_id", id);
            out.put("status", ev.fields().get("status").asText());
            out.put("settled_quantity", ev.fields().has("quantity") ? ev.fields().get("quantity").asText()
                    : settledByStatus(ns, id, ev.fields().get("status").asText()));
            if (ev.fields().has("status_code")) out.put("reason_code", ev.fields().get("status_code").asText());
            out.put("record_version", ev.version());
            return out;
        });
    }

    /**
     * A status without a stated quantity: SETTLED means the whole trade settled, every other status except
     * PARTIALLY_SETTLED means nothing did. PARTIALLY_SETTLED always states its quantity (BundleGuard).
     */
    private String settledByStatus(UUID ns, String tradeId, String status) {
        if (!"SETTLED".equals(status)) return "0";
        return jdbc.sql("SELECT quantity FROM ledger.trades WHERE ns = ? AND id = ?").params(ns, tradeId)
                .query(BigDecimal.class).single().toPlainString();
    }

    public ObjectNode readCustodianStatement(UUID ns, String asOfDate, String isinFilter) {
        String date = Params.date("as_of_date", asOfDate).toString();
        String isin = isinFilter == null ? null : Params.isin("isin", isinFilter);
        return read(ns, row -> {
            ObjectNode out = obj();
            out.put("as_of_date", date);
            ArrayNode lines = out.putArray("lines");
            latest(ns, "CUSTODIAN_STATEMENT").stream()
                    .filter(e -> date.equals(e.fields().path("as_of").asText(null)))
                    .filter(e -> e.fields().has("isin") && e.fields().has("quantity"))
                    .filter(e -> isin == null || isin.equals(e.fields().get("isin").asText()))
                    .sorted(java.util.Comparator.comparing((Ev e) -> e.fields().get("isin").asText()).thenComparing(Ev::id))
                    .forEach(e -> lines.addObject()
                            .put("record_id", e.id())
                            .put("record_version", e.version())
                            .put("isin", e.fields().get("isin").asText())
                            .put("quantity", e.fields().get("quantity").asText()));
            return out;
        });
    }

    private static final Map<String, String> CA_TYPES = Map.of("SPLF", "SPLIT", "SPLR", "REVERSE_SPLIT", "DVCA", "DIVIDEND");

    public ObjectNode readCorporateActions(UUID ns, String isinParam) {
        String isin = Params.isin("isin", isinParam);
        return read(ns, row -> {
            ObjectNode out = obj();
            ArrayNode events = out.putArray("events");
            latest(ns, "CA_NOTICE").stream()
                    .filter(e -> isin.equals(e.fields().path("isin").asText(null)) && e.fields().has("ex_date"))
                    .sorted(java.util.Comparator.comparing((Ev e) -> e.fields().get("ex_date").asText()).thenComparing(Ev::id))
                    .forEach(e -> {
                        ObjectNode n = events.addObject();
                        n.put("ca_event_id", e.id());
                        n.put("isin", isin);
                        n.put("type", CA_TYPES.getOrDefault(e.fields().path("event_type").asText(""), "OTHER"));
                        n.put("ex_date", e.fields().get("ex_date").asText());
                        ratio(e.fields(), "ratio_new").ifPresent(r -> n.put("ratio_numerator", r));
                        ratio(e.fields(), "ratio_old").ifPresent(r -> n.put("ratio_denominator", r));
                        n.put("record_version", e.version());
                    });
            return out;
        });
    }

    /** A ratio leg as an integer, only when the notice states it as a whole number. */
    private static java.util.Optional<Integer> ratio(JsonNode fields, String key) {
        if (!fields.has(key)) return java.util.Optional.empty();
        try {
            return java.util.Optional.of(new BigDecimal(fields.get(key).asText()).intValueExact());
        } catch (ArithmeticException | NumberFormatException e) {
            return java.util.Optional.empty();
        }
    }

    /**
     * One evidence record, latest version. content = JCS of everything the record says (kind, fields, source,
     * receipt time, text) and content_sha256 hashes exactly that string. It is untrusted input (§10).
     */
    public ObjectNode readEvidence(UUID ns, String recordId) {
        String id = Params.id("record_id", recordId);
        return read(ns, row -> jdbc.sql("""
                        SELECT version, kind, fields::text, source_system, observed_at, text FROM ledger.evidence_records
                        WHERE ns = ? AND id = ? ORDER BY version DESC LIMIT 1""")
                .params(ns, id)
                .query((rs, i) -> {
                    ObjectNode content = obj();
                    content.put("kind", rs.getString(2));
                    content.set("fields", parse(rs.getString(3)));
                    content.put("source_system", rs.getString(4));
                    content.put("received_at", utc(rs.getObject(5, OffsetDateTime.class)));
                    content.put("text", rs.getString(6));
                    String canonical = CanonicalJson.canonicalize(content);
                    ObjectNode out = obj();
                    out.put("record_id", id);
                    out.put("version", rs.getInt(1));
                    out.put("kind", rs.getString(2));
                    out.put("untrusted", true);
                    out.put("content", canonical);
                    out.put("content_sha256", Digests.sha256(canonical.getBytes(StandardCharsets.UTF_8)));
                    return out;
                })
                .optional().orElseThrow(ReadService::denied));
    }

    // ---- reference data and FX ------------------------------------------------------------------------------

    /** SECURITY (instrument id), COUNTERPARTY (counterparty id) or SSI (latest SSI_RECORD evidence). */
    public ObjectNode readReferenceData(UUID ns, String recordId) {
        String id = Params.id("record_id", recordId);
        return read(ns, row -> {
            ObjectNode out = obj();
            out.put("record_id", id);
            ObjectNode attrs = Contracts.MAPPER.createObjectNode();
            var security = jdbc.sql("SELECT isin, currency, name FROM ledger.instruments WHERE ns = ? AND id = ?").params(ns, id)
                    .query((rs, i) -> {
                        attrs.put("isin", rs.getString(1));
                        attrs.put("currency", rs.getString(2));
                        putIfPresent(attrs, "name", rs.getString(3));
                        return "SECURITY";
                    }).optional();
            var type = security.or(() -> jdbc.sql("""
                            SELECT c.institution_id, i.name, i.lei FROM ledger.counterparties c
                            JOIN ledger.institutions i ON i.ns = c.ns AND i.id = c.institution_id
                            WHERE c.ns = ? AND c.id = ?""").params(ns, id)
                    .query((rs, i) -> {
                        attrs.put("institution_id", rs.getString(1));
                        attrs.put("name", rs.getString(2));
                        putIfPresent(attrs, "lei", rs.getString(3));
                        return "COUNTERPARTY";
                    }).optional());
            int version = 1;
            if (type.isEmpty()) {
                Ev ssi = latest(ns, "SSI_RECORD").stream().filter(e -> e.id().equals(id)).findFirst().orElseThrow(ReadService::denied);
                ssi.fields().properties().forEach(e -> attrs.put(e.getKey(), e.getValue().asText()));
                version = ssi.version();
                type = java.util.Optional.of("SSI");
            }
            out.put("record_type", type.get());
            out.set("attributes", attrs);
            out.put("record_version", version);
            return out;
        });
    }

    /** The designated-source reference rate for a pair on a date: information only, never an executable price. */
    public ObjectNode readFxSnapshot(UUID ns, String base, String quote, String asOfDate) {
        String b = Params.currency("base", base);
        String q = Params.currency("quote", quote);
        java.time.LocalDate d = Params.date("as_of_date", asOfDate);
        return read(ns, row -> jdbc.sql("""
                        SELECT rate_id, rate, rate_source, as_of FROM ledger.fx_snapshots
                        WHERE ns = ? AND base = ? AND quote = ? AND (as_of AT TIME ZONE 'UTC')::date = ?
                        ORDER BY as_of DESC, rate_id LIMIT 1""")
                .params(ns, b, q, d)
                .query((rs, i) -> {
                    ObjectNode out = obj();
                    out.put("rate_id", rs.getString(1));
                    out.put("base", b);
                    out.put("quote", q);
                    out.put("rate", rs.getBigDecimal(2).toPlainString());
                    out.put("rate_source", rs.getString(3));
                    out.put("as_of", utc(rs.getObject(4, OffsetDateTime.class)));
                    out.put("record_version", 1);  // reference rates are loaded once, never revised in v1
                    return out;
                })
                .optional().orElseThrow(ReadService::denied));
    }

    // ---- helpers --------------------------------------------------------------------------------------------

    private static ObjectNode obj() {
        return Contracts.MAPPER.createObjectNode();
    }

    private static void putIfPresent(ObjectNode n, String key, String value) {
        if (value != null) n.put(key, value);
    }

    private static String utc(OffsetDateTime t) {
        return UTC.format(t.toInstant());
    }

    private static JsonNode parse(String json) {
        return CanonicalJson.parse(json);
    }
}
