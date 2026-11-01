package com.secondline.ledger.positions;

import static com.secondline.ledger.domain.SecuritiesAccount.CUSTODY;
import static com.secondline.ledger.domain.SecuritiesAccount.PENDING;
import static com.secondline.ledger.domain.SecuritiesAccount.STREET;
import static com.secondline.ledger.journal.Side.C;
import static com.secondline.ledger.journal.Side.D;
import static org.assertj.core.api.Assertions.assertThat;

import com.secondline.ledger.LedgerDb;
import com.secondline.ledger.Services;
import com.secondline.ledger.domain.CashAccount;
import com.secondline.ledger.domain.Currency;
import com.secondline.ledger.domain.Isin;
import com.secondline.ledger.domain.Money;
import com.secondline.ledger.domain.Quantity;
import com.secondline.ledger.journal.CashEntry;
import com.secondline.ledger.journal.CashLine;
import com.secondline.ledger.journal.SecuritiesEntry;
import com.secondline.ledger.journal.SecuritiesLine;
import java.time.LocalDate;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** OM-03 §5 ADR-016: positions are projections of the securities ledger, never of cash. */
class OM_03_PositionTest {
    static final Isin ISIN = new Isin("US0000000001");
    final PositionProjection positions = Services.positions();

    @BeforeAll
    static void schema() {
        LedgerDb.migrate();
    }

    static SecuritiesEntry entry(UUID ns, String type, String date, SecuritiesLine... lines) {
        return new SecuritiesEntry(ns, type, LocalDate.parse(date), List.of(lines));
    }

    @Test
    void OM_03_buyThenSettleMovesTradingThenSettled() {
        UUID ns = LedgerDb.newNamespace();
        // docs/domain.md buy: trade date Dr S200 · Cr S900; settlement date Dr S100 · Cr S200
        Services.securities().post(entry(ns, "BUY_TRADE_DATE", "2026-10-01",
                new SecuritiesLine(PENDING, D, ISIN, Quantity.of("100")), new SecuritiesLine(STREET, C, ISIN, Quantity.of("100"))));
        assertThat(positions.stored(ns, ISIN)).isEqualTo(new Position(new java.math.BigDecimal("100"), java.math.BigDecimal.ZERO));
        Services.securities().post(entry(ns, "BUY_SETTLEMENT_DATE", "2026-10-03",
                new SecuritiesLine(CUSTODY, D, ISIN, Quantity.of("100")), new SecuritiesLine(PENDING, C, ISIN, Quantity.of("100"))));
        Position p = positions.stored(ns, ISIN);
        assertThat(p.trading()).isEqualByComparingTo("100");
        assertThat(p.settled()).isEqualByComparingTo("100");
        assertThat(positions.recompute(ns)).containsEntry(ISIN, p);
    }

    @Test
    void OM_03_positionsNeverReadCashLedger() {
        UUID ns = LedgerDb.newNamespace();
        Services.cash().post(new CashEntry(ns, "FEE", LocalDate.parse("2026-10-01"), List.of(
                new CashLine(CashAccount.SECURITIES_AT_COST, D, Money.of("5.00", Currency.USD)),
                new CashLine(CashAccount.FEES_PAYABLE, C, Money.of("5.00", Currency.USD)))));
        assertThat(positions.recompute(ns)).isEmpty();
        assertThat(positions.stored(ns, ISIN)).isEqualTo(Position.ZERO);
    }

    @Test
    void OM_03_securitiesEntryMustBalancePerIsin() {
        UUID ns = LedgerDb.newNamespace();
        org.assertj.core.api.Assertions.assertThatThrownBy(() -> entry(ns, "BAD", "2026-10-01",
                        new SecuritiesLine(PENDING, D, ISIN, Quantity.of("100")),
                        new SecuritiesLine(STREET, C, new Isin("US0000000002"), Quantity.of("100"))))
                .isInstanceOf(com.secondline.ledger.LedgerException.class);
    }
}
