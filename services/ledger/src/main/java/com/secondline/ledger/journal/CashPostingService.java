package com.secondline.ledger.journal;

import com.secondline.ledger.domain.CashAccount;
import com.secondline.ledger.domain.Currency;
import java.math.BigDecimal;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * Posts cash journal entries in one transaction (§5 I1). CashEntry has already proven balance per
 * currency; the DB re-checks at commit. Every failure is a typed LedgerException and writes nothing.
 */
@Service
public class CashPostingService {
    private final JournalRepository repo;
    private final TransactionTemplate tx;

    public CashPostingService(JournalRepository repo, TransactionTemplate tx) {
        this.repo = repo;
        this.tx = tx;
    }

    public UUID post(CashEntry entry) {
        UUID id = UUID.randomUUID();
        Db.domain(() -> tx.execute(s -> {
            repo.insertCash(id, entry, null);
            return id;
        }));
        return id;
    }

    public List<CashLine> lines(UUID ns, UUID entryId) {
        return repo.cashLines(ns, entryId);
    }

    public Map<Currency, BigDecimal> balance(UUID ns, CashAccount account) {
        return repo.cashBalance(ns, account);
    }
}
