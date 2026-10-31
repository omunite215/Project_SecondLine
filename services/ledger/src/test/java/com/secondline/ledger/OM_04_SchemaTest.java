package com.secondline.ledger;

import static com.secondline.ledger.LedgerDb.app;
import static com.secondline.ledger.LedgerDb.exec;
import static com.secondline.ledger.LedgerDb.query;
import static com.secondline.ledger.LedgerDb.stmt;
import static com.secondline.ledger.LedgerDb.superuser;
import static com.secondline.ledger.LedgerDb.tx;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.sql.SQLException;
import java.util.UUID;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** OM-04 §9 ADR-015 ADR-019: V005 load/read columns, version stamping, write-once snapshot, agent_runs. */
class OM_04_SchemaTest {

    @BeforeAll
    static void schema() {
        LedgerDb.migrate();
    }

    static void sqlState(String state, OM_03_SchemaTest.ThrowingRunnable r) {
        assertThatThrownBy(r::run).isInstanceOf(SQLException.class).extracting("SQLState").isEqualTo(state);
    }

    /** One balanced USD cash entry; the app may try to supply committed_version itself. */
    static void postCash(UUID ns, UUID entry, String ref, Long claimedVersion) throws SQLException {
        tx(app(),
                stmt("INSERT INTO ledger.journal_headers (ns, entry_id, entry_type, business_date, ref, committed_version)"
                        + " VALUES (?, ?, 'TRADE', DATE '2026-10-01', coalesce(?, 'jnl_' || substr(md5(random()::text), 1, 16)),"
                        + " coalesce(?, 0))", ns, entry, ref, claimedVersion),
                stmt("INSERT INTO ledger.journal_lines (ns, entry_id, line_no, account_code, currency, side, amount)"
                        + " VALUES (?, ?, 1, '1300', 'USD', 'D', 10.00)", ns, entry),
                stmt("INSERT INTO ledger.journal_lines (ns, entry_id, line_no, account_code, currency, side, amount)"
                        + " VALUES (?, ?, 2, '1110', 'USD', 'C', 10.00)", ns, entry));
    }

    @Test
    void OM_04_committedVersionIsStampedNotSupplied() throws SQLException {
        UUID ns = LedgerDb.newNamespace();
        exec(app(), "UPDATE ledger.namespaces SET state_version = 3 WHERE ns = ?", ns);
        UUID entry = UUID.randomUUID();
        postCash(ns, entry, null, 99L);
        assertThat(query(app(), "SELECT committed_version FROM ledger.journal_headers WHERE ns = ? AND entry_id = ?",
                ns, entry)).isEqualTo("3");
    }

    @Test
    void OM_04_bookingRefsAreOpaqueAndUniquePerNamespace() throws SQLException {
        UUID ns = LedgerDb.newNamespace();
        UUID entry = UUID.randomUUID();
        // The OM-03 services don't name a ref; the DB draws one (hex can't spell dev/eval/blind/test).
        tx(app(),
                stmt("INSERT INTO ledger.securities_entries (ns, entry_id, entry_type, business_date)"
                        + " VALUES (?, ?, 'TRADE', DATE '2026-10-01')", ns, entry),
                stmt("INSERT INTO ledger.securities_lines (ns, entry_id, line_no, account_code, isin, side, quantity)"
                        + " VALUES (?, ?, 1, 'S200', 'US0000000001', 'D', 10)", ns, entry),
                stmt("INSERT INTO ledger.securities_lines (ns, entry_id, line_no, account_code, isin, side, quantity)"
                        + " VALUES (?, ?, 2, 'S900', 'US0000000001', 'C', 10)", ns, entry));
        assertThat(query(app(), "SELECT ref FROM ledger.securities_entries WHERE ns = ? AND entry_id = ?", ns, entry))
                .matches("^mov_[0-9a-f]{16}$");
        postCash(ns, UUID.randomUUID(), "jnl_0000C001", null);
        sqlState("23505", () -> postCash(ns, UUID.randomUUID(), "jnl_0000C001", null));
        postCash(LedgerDb.newNamespace(), UUID.randomUUID(), "jnl_0000C001", null);  // another ns: fine
    }

    @Test
    void OM_04_snapshotIsWriteOnce() throws SQLException {
        UUID ns = UUID.randomUUID();
        exec(app(), "INSERT INTO ledger.namespaces (ns) VALUES (?)", ns);
        assertThat(query(app(), "SELECT status FROM ledger.namespaces WHERE ns = ?", ns)).isEqualTo("EMPTY");
        sqlState("23514", () -> exec(app(), "UPDATE ledger.namespaces SET status = 'LOADED' WHERE ns = ?", ns));
        exec(app(), "UPDATE ledger.namespaces SET snapshot_id = ?, status = 'LOADED', loaded_at = now() WHERE ns = ?",
                "sha256:" + "a".repeat(64), ns);
        sqlState("P0001", () -> exec(app(), "UPDATE ledger.namespaces SET snapshot_id = ? WHERE ns = ?",
                "sha256:" + "b".repeat(64), ns));
        sqlState("42501", () -> exec(app(), "ALTER TABLE ledger.namespaces DROP CONSTRAINT IF EXISTS x"));
        sqlState("42501", () -> exec(app(), "DELETE FROM ledger.namespaces WHERE ns = ?", ns));
    }

    @Test
    void OM_04_agentRunsControlsCheckedAndImmutable() throws SQLException {
        UUID ns = LedgerDb.newNamespace();
        String insert = "INSERT INTO ledger.agent_runs (run_id, ns, controls, agent_id, manifest_ref) VALUES (?, ?, ?,"
                + " 'agt_00000001', 'experiments/manifests/x.json')";
        UUID run = UUID.randomUUID();
        exec(app(), insert, run, ns, "full");
        sqlState("23514", () -> exec(app(), insert, UUID.randomUUID(), ns, "none"));
        sqlState("23503", () -> exec(app(), insert, UUID.randomUUID(), UUID.randomUUID(), "off"));
        sqlState("42501", () -> exec(app(), "UPDATE ledger.agent_runs SET controls = 'off' WHERE run_id = ?", run));
    }

    @Test
    void OM_04_evidenceContentHashIsDerivedNotSupplied() throws SQLException {
        UUID ns = LedgerDb.newNamespace();
        exec(app(), "INSERT INTO ledger.evidence_records (ns, id, version, kind, fields, observed_at, source_system, text)"
                + " VALUES (?, 'evd_00000001', 1, 'NOSTRO_STATEMENT', '{}'::jsonb, now(), 'nostro_sim', 'abc')", ns);
        assertThat(query(app(), "SELECT content_sha256 FROM ledger.evidence_records WHERE ns = ?", ns))
                .isEqualTo("sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
        exec(app(), "INSERT INTO ledger.evidence_records"
                + " (ns, id, version, kind, fields, observed_at, source_system, text, content_sha256)"
                + " VALUES (?, 'evd_00000002', 1, 'NOSTRO_STATEMENT', '{}'::jsonb, now(), 'nostro_sim', 'abc', 'sha256:00')", ns);
        assertThat(query(app(), "SELECT content_sha256 FROM ledger.evidence_records WHERE ns = ? AND id = 'evd_00000002'", ns))
                .startsWith("sha256:ba7816bf");  // a supplied hash is overwritten
    }

    @Test
    void OM_04_breaksCarrySymptomsNotTypes() throws SQLException {
        assertThat(query(superuser(), "SELECT count(*) FROM information_schema.columns WHERE table_schema = 'ledger'"
                + " AND table_name = 'breaks' AND column_name = 'break_type_visible'")).isEqualTo("0");
        UUID ns = LedgerDb.newNamespace();
        sqlState("23514", () -> exec(app(), "INSERT INTO ledger.breaks (ns, id, status, opened_at, symptom)"
                + " VALUES (?, 'brk_00000001', 'OPEN', now(), 'B7_SETTLEMENT_SHORTFALL')", ns));
        exec(app(), "INSERT INTO ledger.breaks (ns, id, status, opened_at, symptom, currency, cash_difference)"
                + " VALUES (?, 'brk_00000002', 'OPEN', now(), 'CASH_DIFFERENCE', 'USD', -0.01)", ns);
    }
}
