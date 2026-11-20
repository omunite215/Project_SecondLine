package com.secondline.ledger.journal;

import com.secondline.ledger.positions.PositionProjection;
import java.util.List;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

/** Posts securities entries and moves the stored positions in the same transaction. */
@Service
public class SecuritiesPostingService {
    private final JournalRepository repo;
    private final PositionProjection positions;
    private final TransactionTemplate tx;

    public SecuritiesPostingService(JournalRepository repo, PositionProjection positions, TransactionTemplate tx) {
        this.repo = repo;
        this.positions = positions;
        this.tx = tx;
    }

    public UUID post(SecuritiesEntry entry) {
        UUID id = UUID.randomUUID();
        Db.domain(() -> tx.execute(s -> {
            repo.insertSecurities(id, entry, null, null);
            positions.apply(entry.ns(), entry.lines());
            return id;
        }));
        return id;
    }

    public List<SecuritiesLine> lines(UUID ns, UUID entryId) {
        return repo.securitiesLines(ns, entryId);
    }
}
