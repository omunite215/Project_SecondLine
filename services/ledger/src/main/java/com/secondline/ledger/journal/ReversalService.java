package com.secondline.ledger.journal;

import com.secondline.ledger.LedgerException;
import com.secondline.ledger.positions.PositionProjection;
import java.util.List;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * Corrections (docs/domain.md "Reversals", T-DOM-05): a new entry with every line's side swapped and
 * reverses_entry_id set, never an edit or delete. One reversal per entry (UNIQUE), never a reversal of a
 * reversal, and always with a reason. It keeps the original's business date (deterministic for replay).
 */
@Service
public class ReversalService {
    private final JournalRepository repo;
    private final PositionProjection positions;
    private final TransactionTemplate tx;

    public ReversalService(JournalRepository repo, PositionProjection positions, TransactionTemplate tx) {
        this.repo = repo;
        this.positions = positions;
        this.tx = tx;
    }

    public UUID reverseCash(UUID ns, UUID entryId, String reason) {
        requireReason(reason);
        UUID id = UUID.randomUUID();
        Db.domain(() -> tx.execute(s -> {
            JournalRepository.Header h = reversible(repo.cashHeader(ns, entryId), entryId);
            List<CashLine> lines = repo.cashLines(ns, entryId).stream().map(CashLine::reversed).toList();
            repo.insertCash(id, new CashEntry(ns, "REVERSAL", h.businessDate(), lines), entryId, reason);
            return id;
        }));
        return id;
    }

    public UUID reverseSecurities(UUID ns, UUID entryId, String reason) {
        requireReason(reason);
        UUID id = UUID.randomUUID();
        Db.domain(() -> tx.execute(s -> {
            JournalRepository.Header h = reversible(repo.securitiesHeader(ns, entryId), entryId);
            List<SecuritiesLine> lines = repo.securitiesLines(ns, entryId).stream().map(SecuritiesLine::reversed).toList();
            repo.insertSecurities(id, new SecuritiesEntry(ns, "REVERSAL", h.businessDate(), lines), entryId, reason);
            positions.apply(ns, lines);
            return id;
        }));
        return id;
    }

    private static void requireReason(String reason) {
        if (reason == null || reason.isBlank()) throw LedgerException.domainInvalid("a reversal needs a reason");
    }

    private static JournalRepository.Header reversible(JournalRepository.Header h, UUID entryId) {
        if (h == null) throw LedgerException.domainInvalid("no entry " + entryId + " in this namespace");
        if (h.reversesEntryId() != null) throw LedgerException.domainInvalid("entry " + entryId + " is itself a reversal");
        return h;
    }
}
