package com.secondline.ledger.journal;

import static com.secondline.ledger.domain.CashAccount.FX_POSITION;
import static com.secondline.ledger.domain.CashAccount.NOSTRO;
import static com.secondline.ledger.domain.CashAccount.PENDING_SETTLEMENT;
import static com.secondline.ledger.domain.CashAccount.SECURITIES_AT_COST;
import static com.secondline.ledger.domain.Currency.EUR;
import static com.secondline.ledger.domain.Currency.USD;
import static com.secondline.ledger.journal.Side.C;
import static com.secondline.ledger.journal.Side.D;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.secondline.ledger.LedgerDb;
import com.secondline.ledger.LedgerException;
import com.secondline.ledger.Services;
import com.secondline.ledger.domain.Money;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** OM-03 §5 I1 I2 T-DOM-01: the cash journal through CashPostingService (docs/domain.md patterns). */
class T_DOM_01_CashPostingTest {
    static final LocalDate TD = LocalDate.parse("2026-10-01");
    final CashPostingService cash = Services.cash();

    @BeforeAll
    static void schema() {
        LedgerDb.migrate();
    }

    static CashLine line(com.secondline.ledger.domain.CashAccount a, Side s, String amt, com.secondline.ledger.domain.Currency c) {
        return new CashLine(a, s, Money.of(amt, c));
    }

    static void invalid(Runnable r) {
        assertThatThrownBy(r::run).isInstanceOf(LedgerException.class)
                .extracting(e -> ((LedgerException) e).code()).isEqualTo("DOMAIN_INVALID");
    }

    @Test
    void T_DOM_01_balancedEntryPosts() {
        UUID ns = LedgerDb.newNamespace();
        // docs/domain.md "buy, trade date": Dr 1300 cost · Cr 1210 pending
        UUID id = cash.post(new CashEntry(ns, "BUY_TRADE_DATE", TD, List.of(
                line(SECURITIES_AT_COST, D, "1000.50", USD), line(PENDING_SETTLEMENT, C, "1000.50", USD))));
        assertThat(cash.lines(ns, id)).containsExactly(
                line(SECURITIES_AT_COST, D, "1000.50", USD), line(PENDING_SETTLEMENT, C, "1000.50", USD));
        assertThat(cash.balance(ns, SECURITIES_AT_COST).get(USD)).isEqualByComparingTo("1000.50");
        assertThat(cash.balance(ns, PENDING_SETTLEMENT).get(USD)).isEqualByComparingTo("-1000.50");
    }

    @Test
    void T_DOM_01_unbalancedEntryRejectedAndNothingWritten() throws Exception {
        UUID ns = LedgerDb.newNamespace();
        invalid(() -> cash.post(new CashEntry(ns, "BAD", TD, List.of(
                line(SECURITIES_AT_COST, D, "10.00", USD), line(PENDING_SETTLEMENT, C, "9.99", USD)))));
        assertThat(LedgerDb.query(LedgerDb.app(), "SELECT count(*) FROM ledger.journal_lines WHERE ns = ?", ns)).isEqualTo("0");
    }

    @Test
    void T_DOM_01_entryNeedsTwoLines() {
        UUID ns = LedgerDb.newNamespace();
        invalid(() -> new CashEntry(ns, "ONE", TD, List.of(line(NOSTRO, D, "1", USD))));
        invalid(() -> new CashEntry(ns, "NONE", TD, List.of()));
    }

    @Test
    void T_DOM_01_scaleAboveMinorUnitsRejected() {
        invalid(() -> Money.of("10.001", USD));
        invalid(() -> Money.of("10.5", com.secondline.ledger.domain.Currency.JPY));
    }

    @Test
    void T_DOM_01_fxConversionBalancesPerCurrency() {
        UUID ns = LedgerDb.newNamespace();
        // docs/domain.md FX conversion USD→EUR: USD Dr 1500 · Cr 1110; EUR Dr 1110 · Cr 1500
        cash.post(new CashEntry(ns, "FX_CONVERSION", TD, List.of(
                line(FX_POSITION, D, "1000.00", USD), line(NOSTRO, C, "1000.00", USD),
                line(NOSTRO, D, "919.60", EUR), line(FX_POSITION, C, "919.60", EUR))));
        invalid(() -> cash.post(new CashEntry(ns, "FX_WRONG", TD, List.of(
                line(FX_POSITION, D, "1000.00", USD), line(NOSTRO, C, "919.60", EUR)))));
        assertThat(cash.balance(ns, NOSTRO)).containsOnlyKeys(USD, EUR);
    }

    @Test
    void OM_03_postingInUnknownNamespaceRejected() {
        invalid(() -> cash.post(new CashEntry(UUID.randomUUID(), "GHOST", TD, List.of(
                line(NOSTRO, D, "1.00", USD), line(PENDING_SETTLEMENT, C, "1.00", USD)))));
    }
}
