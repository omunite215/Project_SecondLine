package com.secondline.ledger.journal;

import static com.secondline.ledger.domain.CashAccount.PENDING_SETTLEMENT;
import static com.secondline.ledger.domain.CashAccount.SECURITIES_AT_COST;
import static com.secondline.ledger.domain.Currency.USD;
import static com.secondline.ledger.journal.Side.C;
import static com.secondline.ledger.journal.Side.D;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.secondline.ledger.LedgerDb;
import com.secondline.ledger.LedgerException;
import com.secondline.ledger.Services;
import com.secondline.ledger.domain.Isin;
import com.secondline.ledger.domain.Money;
import com.secondline.ledger.domain.Quantity;
import com.secondline.ledger.domain.SecuritiesAccount;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** OM-03 §5 T-DOM-05 SEC-12: corrections are full reversals; history keeps the original. */
class T_DOM_05_ReversalTest {
    static final LocalDate TD = LocalDate.parse("2026-10-01");
    static final Isin ISIN = new Isin("US0000000001");
    final CashPostingService cash = Services.cash();
    final SecuritiesPostingService sec = Services.securities();
    final ReversalService rev = Services.reversals();

    @BeforeAll
    static void schema() {
        LedgerDb.migrate();
    }

    static CashEntry buy(UUID ns, String amount) {
        return new CashEntry(ns, "BUY_TRADE_DATE", TD, List.of(
                new CashLine(SECURITIES_AT_COST, D, Money.of(amount, USD)),
                new CashLine(PENDING_SETTLEMENT, C, Money.of(amount, USD))));
    }

    static SecuritiesEntry buyQty(UUID ns, String qty) {
        return new SecuritiesEntry(ns, "BUY_TRADE_DATE", TD, List.of(
                new SecuritiesLine(SecuritiesAccount.PENDING, D, ISIN, Quantity.of(qty)),
                new SecuritiesLine(SecuritiesAccount.STREET, C, ISIN, Quantity.of(qty))));
    }

    static String rows(UUID ns, UUID entry) throws Exception {
        return LedgerDb.query(LedgerDb.superuser(), "SELECT string_agg(t::text, '|' ORDER BY t::text) FROM ("
                + " SELECT h::text AS t FROM ledger.journal_headers h WHERE ns = ? AND entry_id = ?"
                + " UNION ALL SELECT l::text FROM ledger.journal_lines l WHERE ns = ? AND entry_id = ?) x",
                ns, entry, ns, entry);
    }

    static void invalid(Runnable r) {
        assertThatThrownBy(r::run).isInstanceOf(LedgerException.class)
                .extracting(e -> ((LedgerException) e).code()).isEqualTo("DOMAIN_INVALID");
    }

    @Test
    void T_DOM_05_reversalKeepsOriginal() throws Exception {
        UUID ns = LedgerDb.newNamespace();
        UUID original = cash.post(buy(ns, "1000.50"));
        String before = rows(ns, original);
        UUID reversal = rev.reverseCash(ns, original, "booked against the wrong trade");
        assertThat(rows(ns, original)).isEqualTo(before);
        assertThat(cash.lines(ns, reversal)).containsExactlyElementsOf(
                cash.lines(ns, original).stream().map(CashLine::reversed).toList());
        assertThat(cash.balance(ns, SECURITIES_AT_COST).get(USD)).isEqualByComparingTo("0");
        assertThat(LedgerDb.query(LedgerDb.app(), "SELECT reverses_entry_id::text || '/' || reason FROM ledger.journal_headers"
                + " WHERE ns = ? AND entry_id = ?", ns, reversal)).isEqualTo(original + "/booked against the wrong trade");
    }

    @Test
    void T_DOM_05_reversePlusRebookLeavesBothInHistory() throws Exception {
        // docs/domain.md B2: reverse the wrong booking, rebook at the evidenced quantity.
        UUID ns = LedgerDb.newNamespace();
        UUID wrong = sec.post(buyQty(ns, "1000"));
        rev.reverseSecurities(ns, wrong, "custodian confirms 900");
        sec.post(buyQty(ns, "900"));
        assertThat(LedgerDb.query(LedgerDb.app(), "SELECT count(*) FROM ledger.securities_entries WHERE ns = ?", ns)).isEqualTo("3");
        assertThat(Services.positions().stored(ns, ISIN).trading()).isEqualByComparingTo("900");
    }

    @Test
    void T_DOM_05_secondReversalRejected() {
        UUID ns = LedgerDb.newNamespace();
        UUID original = cash.post(buy(ns, "10.00"));
        rev.reverseCash(ns, original, "first");
        invalid(() -> rev.reverseCash(ns, original, "second"));
    }

    @Test
    void T_DOM_05_reversalOfReversalRejected() {
        UUID ns = LedgerDb.newNamespace();
        UUID original = cash.post(buy(ns, "10.00"));
        UUID reversal = rev.reverseCash(ns, original, "first");
        invalid(() -> rev.reverseCash(ns, reversal, "undo the undo"));
        UUID s = sec.post(buyQty(ns, "5"));
        UUID sr = rev.reverseSecurities(ns, s, "first");
        invalid(() -> rev.reverseSecurities(ns, sr, "undo the undo"));
    }

    @Test
    void T_DOM_05_reversalNeedsReason() {
        UUID ns = LedgerDb.newNamespace();
        UUID original = cash.post(buy(ns, "10.00"));
        invalid(() -> rev.reverseCash(ns, original, " "));
    }

    @Test
    void OM_03_reversalAcrossNamespacesRejected() {
        UUID a = LedgerDb.newNamespace();
        UUID b = LedgerDb.newNamespace();
        UUID original = cash.post(buy(a, "10.00"));
        invalid(() -> rev.reverseCash(b, original, "wrong namespace"));
        invalid(() -> rev.reverseCash(a, UUID.randomUUID(), "no such entry"));
    }
}
