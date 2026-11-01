package com.secondline.ledger.ns;

import com.secondline.contracts.generated.ErrorCode;
import com.secondline.ledger.LedgerException;
import java.util.Optional;
import java.util.UUID;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

/**
 * Namespace lifecycle (ADR-015): EMPTY → LOADED → RETIRED. Rows are never deleted (ADR-019); the DB keeps
 * the snapshot write-once and state_version forward-only (V005 namespace_guard).
 */
@Repository
public class NamespaceRepository {
    public enum Status { EMPTY, LOADED, RETIRED }

    public record Row(UUID ns, Status status, String snapshotId, long stateVersion) {}

    private final JdbcClient jdbc;

    public NamespaceRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    public UUID create() {
        UUID ns = UUID.randomUUID();
        jdbc.sql("INSERT INTO ledger.namespaces (ns) VALUES (?)").param(ns).update();
        return ns;
    }

    public Optional<Row> find(UUID ns) {
        return jdbc.sql("SELECT status, snapshot_id, state_version FROM ledger.namespaces WHERE ns = ?").param(ns)
                .query((rs, i) -> new Row(ns, Status.valueOf(rs.getString(1)), rs.getString(2), rs.getLong(3)))
                .optional();
    }

    /** Row-locks the namespace for the rest of the caller's transaction (serialises loads and version bumps). */
    public Optional<Row> lock(UUID ns) {
        return jdbc.sql("SELECT status, snapshot_id, state_version FROM ledger.namespaces WHERE ns = ? FOR UPDATE").param(ns)
                .query((rs, i) -> new Row(ns, Status.valueOf(rs.getString(1)), rs.getString(2), rs.getLong(3)))
                .optional();
    }

    /** A LOADED namespace, or PERMISSION_DENIED: unknown, empty and retired look the same to every caller. */
    public Row requireLoaded(UUID ns) {
        return find(ns).filter(r -> r.status() == Status.LOADED)
                .orElseThrow(() -> new LedgerException(ErrorCode.PERMISSION_DENIED, "namespace not available"));
    }

    public void markLoaded(UUID ns, String snapshotId) {
        jdbc.sql("UPDATE ledger.namespaces SET snapshot_id = ?, status = 'LOADED', loaded_at = now() WHERE ns = ?")
                .params(snapshotId, ns).update();
    }

    /** Next ns state version; call once per committed domain transaction, inside it (OM-08). */
    public long bumpVersion(UUID ns) {
        return jdbc.sql("UPDATE ledger.namespaces SET state_version = state_version + 1 WHERE ns = ? AND status = 'LOADED'"
                        + " RETURNING state_version").param(ns)
                .query(Long.class).optional()
                .orElseThrow(() -> new LedgerException(ErrorCode.PERMISSION_DENIED, "namespace not available"));
    }

    public void retire(UUID ns) {
        int n = jdbc.sql("UPDATE ledger.namespaces SET status = 'RETIRED' WHERE ns = ?").param(ns).update();
        if (n == 0) throw new LedgerException(ErrorCode.PERMISSION_DENIED, "namespace not available");
    }
}
