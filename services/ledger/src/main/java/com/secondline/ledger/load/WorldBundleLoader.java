package com.secondline.ledger.load;

import com.fasterxml.jackson.databind.JsonNode;
import com.secondline.contracts.Digests;
import com.secondline.contracts.generated.ErrorCode;
import com.secondline.ledger.LedgerException;
import com.secondline.ledger.domain.CashAccount;
import com.secondline.ledger.domain.Currency;
import com.secondline.ledger.domain.Isin;
import com.secondline.ledger.domain.Money;
import com.secondline.ledger.domain.Quantity;
import com.secondline.ledger.domain.SecuritiesAccount;
import com.secondline.ledger.journal.BookingRef;
import com.secondline.ledger.journal.CashEntry;
import com.secondline.ledger.journal.CashLine;
import com.secondline.ledger.journal.CashPostingService;
import com.secondline.ledger.journal.Db;
import com.secondline.ledger.journal.SecuritiesEntry;
import com.secondline.ledger.journal.SecuritiesLine;
import com.secondline.ledger.journal.SecuritiesPostingService;
import com.secondline.ledger.journal.Side;
import com.secondline.ledger.ns.NamespaceRepository;
import com.secondline.ledger.ns.NamespaceRepository.Status;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * Loads a WorldBundle into an EMPTY namespace in ONE transaction (OM-04 §5 §9, ADR-015, REQ-011).
 * BundleGuard runs first, outside the transaction. The ns row is locked, so concurrent loads serialise:
 * the same bundle again is a no-op, a different one is IDEMPOTENCY_CONFLICT (the ns is the key, the bundle
 * hash the digest). Ledger entries go through the OM-03 posting services, so balance per currency/ISIN,
 * minor-unit scale and the position projection are checked exactly as for any other posting.
 * Evidence is stored once, as given; the settlement/custodian/CA read tools query it by kind.
 */
@Service
public class WorldBundleLoader {
    private final JdbcClient jdbc;
    private final BundleGuard guard;
    private final NamespaceRepository namespaces;
    private final CashPostingService cash;
    private final SecuritiesPostingService securities;
    private final TransactionTemplate tx;

    public WorldBundleLoader(JdbcClient jdbc, BundleGuard guard, NamespaceRepository namespaces, CashPostingService cash,
                             SecuritiesPostingService securities, TransactionTemplate tx) {
        this.jdbc = jdbc;
        this.guard = guard;
        this.namespaces = namespaces;
        this.cash = cash;
        this.securities = securities;
        this.tx = tx;
    }

    public LoadResult load(UUID ns, JsonNode bundle) {
        guard.check(bundle);
        String snapshot = Digests.sha256Canonical(bundle);
        return Db.domain(() -> tx.execute(s -> {
            NamespaceRepository.Row row = namespaces.lock(ns)
                    .filter(r -> r.status() != Status.RETIRED)
                    .orElseThrow(() -> new LedgerException(ErrorCode.PERMISSION_DENIED, "namespace not available"));
            if (row.status() == Status.LOADED) {
                if (!snapshot.equals(row.snapshotId())) {
                    throw new LedgerException(ErrorCode.IDEMPOTENCY_CONFLICT, "namespace already holds a different bundle");
                }
                return new LoadResult(ns, snapshot, row.stateVersion(), true);
            }
            write(ns, bundle);
            namespaces.markLoaded(ns, snapshot);
            return new LoadResult(ns, snapshot, row.stateVersion(), false);
        }));
    }

    private void write(UUID ns, JsonNode b) {
        for (JsonNode r : b.get("reference_snapshots")) {
            String ref = r.get("ref").asText();
            jdbc.sql("INSERT INTO ledger.reference_data_versions (ns, id, source, version, license, sha256, ref, retrieved_at)"
                            + " VALUES (?, ?, ?, ?, ?, ?, ?, ?)")
                    .params(ns, "ref_" + Digests.sha256(ref.getBytes(java.nio.charset.StandardCharsets.UTF_8)).substring(7, 23),
                            r.get("source").asText(), ref.substring(ref.indexOf('@') + 1), r.get("license").asText(),
                            r.get("sha256").asText(), ref, instant(r, "retrieved_at"))
                    .update();
        }
        for (JsonNode i : b.get("institutions")) {
            jdbc.sql("INSERT INTO ledger.institutions (ns, id, name, lei) VALUES (?, ?, ?, ?)")
                    .params(ns, text(i, "institution_id"), text(i, "name"), text(i, "lei")).update();
        }
        for (JsonNode c : b.get("counterparties")) {
            jdbc.sql("INSERT INTO ledger.counterparties (ns, id, institution_id) VALUES (?, ?, ?)")
                    .params(ns, text(c, "counterparty_id"), text(c, "institution_id")).update();
        }
        for (JsonNode i : b.get("instruments")) {
            jdbc.sql("INSERT INTO ledger.instruments (ns, id, isin, currency, name) VALUES (?, ?, ?, ?, ?)")
                    .params(ns, instrumentId(text(i, "isin")), text(i, "isin"), text(i, "currency"), text(i, "name")).update();
        }
        for (JsonNode a : b.get("accounts")) {
            if (!"cash".equals(text(a, "kind"))) continue;  // securities accounts are per ISIN, implied by the lines
            String[] code = text(a, "account").split("-");
            jdbc.sql("INSERT INTO ledger.cash_accounts (ns, code, currency) VALUES (?, ?, ?)").params(ns, code[0], code[1]).update();
        }
        for (JsonNode f : b.get("fx_rates")) {
            jdbc.sql("INSERT INTO ledger.fx_snapshots (ns, rate_id, base, quote, rate, rate_source, as_of)"
                            + " VALUES (?, ?, ?, ?, ?::numeric, ?, ?)")
                    .params(ns, text(f, "rate_id"), text(f, "base"), text(f, "quote"), text(f, "rate"), text(f, "source"),
                            LocalDate.parse(text(f, "as_of")).atStartOfDay().atOffset(ZoneOffset.UTC))
                    .update();
        }
        for (JsonNode t : b.get("trades")) {
            jdbc.sql("INSERT INTO ledger.trades (ns, id, instrument_id, counterparty_id, side, quantity, price, currency,"
                            + " trade_date, settlement_date, record_version, status)"
                            + " VALUES (?, ?, ?, ?, ?, ?::numeric, ?::numeric, ?, ?, ?, ?, ?)")
                    .params(ns, text(t, "trade_id"), instrumentId(text(t, "isin")), text(t, "counterparty_id"), text(t, "side"),
                            text(t, "quantity"), text(t, "price"), text(t, "currency"), LocalDate.parse(text(t, "trade_date")),
                            LocalDate.parse(text(t, "settlement_date")), t.get("version").asInt(), text(t, "status"))
                    .update();
        }
        for (JsonNode e : b.get("journal_entries")) {
            List<CashLine> lines = new ArrayList<>();
            for (JsonNode l : e.get("lines")) {
                Currency ccy = Currency.of(text(l, "currency"));
                lines.add(new CashLine(CashAccount.fromCode(text(l, "account").split("-")[0]), side(l),
                        Money.of(text(l, "amount"), ccy)));
            }
            cash.post(new CashEntry(ns, text(e, "entry_type"), LocalDate.parse(text(e, "effective_date")), lines),
                    new BookingRef(text(e, "entry_id"), text(e, "trade_id"), instant(e, "booked_at")));
        }
        for (List<JsonNode> group : movementsByEntry(b.get("securities_movements")).values()) {
            JsonNode first = group.get(0);
            List<SecuritiesLine> lines = new ArrayList<>();
            for (JsonNode m : group) {
                for (String k : List.of("entry_type", "effective_date", "booked_at", "trade_id")) {
                    if (!java.util.Objects.equals(text(m, k), text(first, k))) {
                        throw LedgerException.domainInvalid("movements of entry " + text(first, "entry_id") + " disagree on " + k);
                    }
                }
                lines.add(new SecuritiesLine(SecuritiesAccount.fromCode(text(m, "account").split("-")[0]), side(m),
                        new Isin(text(m, "isin")), Quantity.of(text(m, "quantity"))));
            }
            securities.post(new SecuritiesEntry(ns, text(first, "entry_type"), LocalDate.parse(text(first, "effective_date")), lines),
                    new BookingRef(text(first, "entry_id"), text(first, "trade_id"), instant(first, "booked_at")));
        }
        for (JsonNode e : b.get("evidence")) {
            jdbc.sql("INSERT INTO ledger.evidence_records (ns, id, version, kind, fields, observed_at, source_system, text)"
                            + " VALUES (?, ?, ?, ?, ?::jsonb, ?, ?, ?)")
                    .params(ns, text(e, "record_id"), e.get("version").asInt(), text(e, "kind"), e.get("fields").toString(),
                            instant(e, "received_at"), text(e, "source_system"), text(e, "text"))
                    .update();
        }
        for (JsonNode k : b.get("breaks")) {
            String id = text(k, "break_id");
            jdbc.sql("INSERT INTO ledger.breaks (ns, id, status, opened_at, symptom, currency, isin, cash_difference,"
                            + " quantity_difference) VALUES (?, ?, 'OPEN', ?, ?, ?, ?, ?::numeric, ?::numeric)")
                    .params(ns, id, instant(k, "opened_at"), text(k, "symptom"), text(k, "currency"), text(k, "isin"),
                            text(k, "cash_difference"), text(k, "quantity_difference"))
                    .update();
            for (JsonNode t : k.path("trade_ids")) {
                jdbc.sql("INSERT INTO ledger.break_trades (ns, break_id, trade_id) VALUES (?, ?, ?)").params(ns, id, t.asText()).update();
            }
            for (JsonNode ev : k.path("evidence_ids")) {
                jdbc.sql("INSERT INTO ledger.break_evidence (ns, break_id, record_id) VALUES (?, ?, ?)").params(ns, id, ev.asText()).update();
            }
        }
    }

    /** Bundle order preserved, so entries post in the order the factory wrote them. */
    private static Map<String, List<JsonNode>> movementsByEntry(JsonNode movements) {
        Map<String, List<JsonNode>> out = new LinkedHashMap<>();
        for (JsonNode m : movements) out.computeIfAbsent(text(m, "entry_id"), k -> new ArrayList<>()).add(m);
        return out;
    }

    /** Instruments are keyed by ISIN in the bundle; the ledger's opaque id is derived from it. */
    static String instrumentId(String isin) {
        return "isn_" + isin;
    }

    private static Side side(JsonNode line) {
        return "DR".equals(text(line, "side")) ? Side.D : Side.C;
    }

    private static String text(JsonNode n, String key) {
        JsonNode v = n.get(key);
        return v == null || v.isNull() ? null : v.asText();
    }

    private static OffsetDateTime instant(JsonNode n, String key) {
        return OffsetDateTime.parse(text(n, key));
    }
}
