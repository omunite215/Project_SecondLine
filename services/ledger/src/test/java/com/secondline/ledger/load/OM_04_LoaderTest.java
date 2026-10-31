package com.secondline.ledger.load;

import static com.secondline.ledger.LedgerDb.app;
import static com.secondline.ledger.LedgerDb.query;
import static com.secondline.ledger.Bundles.minimal;
import static com.secondline.ledger.Bundles.with;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;

import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.secondline.contracts.Digests;
import com.secondline.contracts.generated.ErrorCode;
import com.secondline.ledger.LedgerDb;
import com.secondline.ledger.LedgerException;
import com.secondline.ledger.Services;
import com.secondline.ledger.domain.Isin;
import com.secondline.ledger.positions.Position;
import java.math.BigDecimal;
import java.sql.SQLException;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** OM-04 §5 §9 REQ-011 ADR-015: a WorldBundle loads into an EMPTY ns in one transaction, idempotent by hash. */
class OM_04_LoaderTest {
    static final WorldBundleLoader LOADER = Services.loader();

    @BeforeAll
    static void schema() {
        LedgerDb.migrate();
    }

    static UUID emptyNs() {
        return Services.namespaces().create();
    }

    static ErrorCode code(Runnable r) {
        Throwable t = catchThrowable(r::run);
        assertThat(t).isInstanceOf(LedgerException.class);
        return ((LedgerException) t).code();
    }

    static String count(String table, UUID ns) throws SQLException {
        return query(app(), "SELECT count(*) FROM ledger." + table + " WHERE ns = ?", ns);
    }

    @Test
    void OM_04_loadMinimalBundle() throws SQLException {
        UUID ns = emptyNs();
        LoadResult r = LOADER.load(ns, minimal());
        assertThat(r.alreadyLoaded()).isFalse();
        assertThat(r.snapshotHash()).isEqualTo(Digests.sha256Canonical(minimal()));
        assertThat(r.stateVersion()).isZero();
        assertThat(query(app(), "SELECT status FROM ledger.namespaces WHERE ns = ?", ns)).isEqualTo("LOADED");
        assertThat(Services.positions().stored(ns, new Isin("XS0000000012")))
                .isEqualTo(new Position(new BigDecimal("300"), new BigDecimal("300")));
        assertThat(Services.positions().recompute(ns).get(new Isin("XS0000000012")))
                .isEqualTo(Services.positions().stored(ns, new Isin("XS0000000012")));
        assertThat(query(app(), "SELECT ref || '|' || trade_id || '|' || entry_type || '|' || business_date || '|' || committed_version"
                + " FROM ledger.journal_headers WHERE ns = ?", ns)).isEqualTo("jnl_0000C001|trd_0000B001|SETTLEMENT|2026-02-27|0");
        assertThat(query(app(), "SELECT ref FROM ledger.securities_entries WHERE ns = ?", ns)).isEqualTo("sec_0000D001");
        assertThat(query(app(), "SELECT counterparty_id || '|' || status FROM ledger.trades WHERE ns = ?", ns))
                .isEqualTo("cpt_0000H001|SETTLED");
        assertThat(count("evidence_records", ns)).isEqualTo("3");
        assertThat(query(app(), "SELECT status || '|' || symptom || '|' || cash_difference FROM ledger.breaks WHERE ns = ?", ns))
                .isEqualTo("OPEN|CASH_DIFFERENCE|-0.01");
        assertThat(count("break_evidence", ns)).isEqualTo("3");
        assertThat(count("break_trades", ns)).isEqualTo("1");
    }

    @Test
    void OM_04_reloadSameBundleIsNoop() throws SQLException {
        UUID ns = emptyNs();
        LoadResult first = LOADER.load(ns, minimal());
        LoadResult again = LOADER.load(ns, minimal());
        assertThat(again.alreadyLoaded()).isTrue();
        assertThat(again.snapshotHash()).isEqualTo(first.snapshotHash());
        assertThat(count("journal_headers", ns)).isEqualTo("1");
        assertThat(count("trades", ns)).isEqualTo("1");
    }

    @Test
    void OM_04_reloadDifferentBundleConflicts() {
        UUID ns = emptyNs();
        LOADER.load(ns, minimal());
        ObjectNode other = with(b -> ((ObjectNode) b.at("/breaks/0")).put("opened_at", "2026-03-02T17:00:00Z"));
        assertThat(code(() -> LOADER.load(ns, other))).isEqualTo(ErrorCode.IDEMPOTENCY_CONFLICT);
    }

    @Test
    void OM_04_unknownOrRetiredNamespaceDenied() {
        assertThat(code(() -> LOADER.load(UUID.randomUUID(), minimal()))).isEqualTo(ErrorCode.PERMISSION_DENIED);
        UUID ns = emptyNs();
        Services.namespaces().retire(ns);
        assertThat(code(() -> LOADER.load(ns, minimal()))).isEqualTo(ErrorCode.PERMISSION_DENIED);
    }

    @Test
    void OM_04_unbalancedBundleRollsBackEverything() throws SQLException {
        UUID ns = emptyNs();
        ObjectNode bad = with(b -> ((ObjectNode) b.at("/journal_entries/0/lines/1")).put("amount", "3703.69"));
        assertThat(code(() -> LOADER.load(ns, bad))).isEqualTo(ErrorCode.DOMAIN_INVALID);
        assertThatNothingWritten(ns);
    }

    @Test
    void OM_04_scaleAboveMinorUnitsRejectedNotRounded() throws SQLException {
        UUID ns = emptyNs();
        ObjectNode bad = with(b -> {
            ((ObjectNode) b.at("/journal_entries/0/lines/0")).put("amount", "3703.685");
            ((ObjectNode) b.at("/journal_entries/0/lines/1")).put("amount", "3703.685");
        });
        assertThat(code(() -> LOADER.load(ns, bad))).isEqualTo(ErrorCode.DOMAIN_INVALID);
        assertThatNothingWritten(ns);
    }

    @Test
    void OM_04_movementsOfOneEntryMustAgree() throws SQLException {
        UUID ns = emptyNs();
        ObjectNode bad = with(b -> ((ObjectNode) b.at("/securities_movements/1")).put("effective_date", "2026-02-28"));
        assertThat(code(() -> LOADER.load(ns, bad))).isEqualTo(ErrorCode.DOMAIN_INVALID);
        assertThatNothingWritten(ns);
    }

    @Test
    void OM_04_unbalancedSecuritiesEntryRejected() throws SQLException {
        UUID ns = emptyNs();
        ObjectNode bad = with(b -> ((ArrayNode) b.get("securities_movements")).remove(1));
        assertThat(code(() -> LOADER.load(ns, bad))).isEqualTo(ErrorCode.DOMAIN_INVALID);
        assertThatNothingWritten(ns);
    }

    @Test
    void OM_04_guardRejectionWritesNothing() throws SQLException {
        UUID ns = emptyNs();
        assertThat(code(() -> LOADER.load(ns, with(b -> b.put("root_cause", "x"))))).isEqualTo(ErrorCode.DOMAIN_INVALID);
        assertThatNothingWritten(ns);
    }

    @Test
    void OM_04_concurrentLoadsOfOneBundleLoadOnce() throws Exception {
        UUID ns = emptyNs();
        ExecutorService pool = Executors.newFixedThreadPool(4);
        try {
            List<Callable<LoadResult>> jobs = List.of(() -> LOADER.load(ns, minimal()), () -> LOADER.load(ns, minimal()),
                    () -> LOADER.load(ns, minimal()), () -> LOADER.load(ns, minimal()));
            long fresh = 0;
            for (Future<LoadResult> f : pool.invokeAll(jobs)) fresh += f.get().alreadyLoaded() ? 0 : 1;
            assertThat(fresh).isEqualTo(1);
        } finally {
            pool.shutdownNow();
        }
        assertThat(count("trades", ns)).isEqualTo("1");
        assertThat(count("journal_headers", ns)).isEqualTo("1");
    }

    static void assertThatNothingWritten(UUID ns) throws SQLException {
        assertThat(query(app(), "SELECT status FROM ledger.namespaces WHERE ns = ?", ns)).isEqualTo("EMPTY");
        for (String t : List.of("institutions", "trades", "journal_headers", "securities_entries", "evidence_records",
                "breaks", "positions", "cash_accounts", "fx_snapshots", "reference_data_versions")) {
            assertThat(count(t, ns)).as(t).isEqualTo("0");
        }
    }
}
