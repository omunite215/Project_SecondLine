package com.secondline.ledger.journal;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.secondline.ledger.LedgerDb;
import com.secondline.ledger.LedgerException;
import com.secondline.ledger.Services;
import com.secondline.ledger.domain.CashAccount;
import com.secondline.ledger.domain.Currency;
import com.secondline.ledger.domain.Isin;
import com.secondline.ledger.domain.Money;
import com.secondline.ledger.domain.Quantity;
import com.secondline.ledger.domain.SecuritiesAccount;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import net.jqwik.api.Arbitraries;
import net.jqwik.api.Arbitrary;
import net.jqwik.api.Combinators;
import net.jqwik.api.ForAll;
import net.jqwik.api.Property;
import net.jqwik.api.Provide;
import net.jqwik.api.lifecycle.BeforeContainer;

/**
 * OM-03 T-DOM-01 T-DOM-05 I1 I2 (ADR-016 verification: 10k generated entries). Pure properties run 10k
 * tries; DB-backed ones 200 (Om's laptop), each in a fresh namespace.
 */
class T_DOM_01_PropertiesTest {
    static final UUID NS = UUID.fromString("00000000-0000-4000-8000-000000000000"); // pure tests never hit the DB
    static final LocalDate TD = LocalDate.parse("2026-10-01");
    static final List<Isin> ISINS = List.of(new Isin("US0000000001"), new Isin("GB0000000002"), new Isin("CH0000000003"));

    @BeforeContainer
    static void schema() {
        LedgerDb.migrate();
    }

    /** An amount with exactly the currency's minor units, 0.01 .. 99,999.99 (JPY 1 .. 9,999,999). */
    static Arbitrary<BigDecimal> amount(Currency c) {
        return Arbitraries.longs().between(1, 9_999_999).map(n -> BigDecimal.valueOf(n, c.minorUnits()));
    }

    /** Lines for one currency: 1–3 debits, and credits that split the same total into 1–3 parts. */
    static Arbitrary<List<CashLine>> balancedIn(Currency c) {
        Arbitrary<CashAccount> acct = Arbitraries.of(CashAccount.values());
        return amount(c).list().ofMinSize(1).ofMaxSize(3).flatMap(debits -> {
            BigDecimal total = debits.stream().reduce(BigDecimal.ZERO, BigDecimal::add);
            BigDecimal unit = BigDecimal.ONE.movePointLeft(c.minorUnits());
            long units = total.divide(unit).longValueExact();
            Arbitrary<List<BigDecimal>> split = units < 2 ? Arbitraries.just(List.of(total)) : // one unit can't be split
                    Arbitraries.integers().between(1, (int) Math.min(3, units)).flatMap(parts ->
                    Arbitraries.longs().between(1, units - 1).list().ofSize(parts - 1).uniqueElements().map(cuts -> {
                        List<Long> sorted = new ArrayList<>(cuts);
                        sorted.sort(null);
                        List<BigDecimal> credits = new ArrayList<>();
                        long prev = 0;
                        for (long cut : sorted) {
                            credits.add(BigDecimal.valueOf(cut - prev, c.minorUnits()));
                            prev = cut;
                        }
                        credits.add(BigDecimal.valueOf(units - prev, c.minorUnits()));
                        return credits;
                    }));
            return split.flatMap(credits -> acct.list().ofSize(debits.size() + credits.size()).map(accounts -> {
                        List<CashLine> lines = new ArrayList<>();
                        int i = 0;
                        for (BigDecimal d : debits) lines.add(new CashLine(accounts.get(i++), Side.D, new Money(d, c)));
                        for (BigDecimal cr : credits) lines.add(new CashLine(accounts.get(i++), Side.C, new Money(cr, c)));
                        return lines;
                    }));
        });
    }

    @Provide
    Arbitrary<List<CashLine>> balancedLines() {
        return Arbitraries.of(Currency.values()).set().ofMinSize(1).ofMaxSize(3).flatMap(ccys -> {
            List<Arbitrary<List<CashLine>>> per = ccys.stream().map(T_DOM_01_PropertiesTest::balancedIn).toList();
            return Combinators.combine(per).as(parts -> parts.stream().flatMap(List::stream).toList());
        });
    }

    static void rejected(Runnable r) {
        assertThatThrownBy(r::run).isInstanceOf(LedgerException.class);
    }

    @Property(tries = 10000)
    void T_DOM_01_generatedBalancedEntriesValidate(@ForAll("balancedLines") List<CashLine> lines,
                                                    @ForAll("index") int pick) {
        new CashEntry(NS, "GEN", TD, lines);
        CashLine l = lines.get(pick % lines.size());
        BigDecimal unit = BigDecimal.ONE.movePointLeft(l.money().currency().minorUnits());
        List<CashLine> off = new ArrayList<>(lines);
        off.set(pick % lines.size(), new CashLine(l.account(), l.side(), new Money(l.money().amount().add(unit), l.money().currency())));
        rejected(() -> new CashEntry(NS, "GEN_OFF_BY_ONE_UNIT", TD, off));
    }

    @Property(tries = 10000)
    void T_DOM_01_crossCurrencyOffsetsRejected(@ForAll("balancedLines") List<CashLine> lines,
                                               @ForAll Currency a, @ForAll Currency b) {
        // +1 whole unit debit in A and +1 credit in B nets to zero overall, but not per currency (I1).
        if (a == b) return;
        List<CashLine> moved = new ArrayList<>(lines);
        moved.add(new CashLine(CashAccount.NOSTRO, Side.D, new Money(BigDecimal.ONE, a)));
        moved.add(new CashLine(CashAccount.NOSTRO, Side.C, new Money(BigDecimal.ONE, b)));
        rejected(() -> new CashEntry(NS, "CROSS_CCY", TD, moved));
    }

    @Property(tries = 10000)
    void T_DOM_01_precisionPerCurrency(@ForAll Currency c, @ForAll("lastDigit") int digit) {
        BigDecimal tooFine = BigDecimal.valueOf(100L * 10 + digit, c.minorUnits() + 1);
        rejected(() -> new Money(tooFine, c));
    }

    @Provide
    Arbitrary<Integer> index() {
        return Arbitraries.integers().between(0, 1000);
    }

    @Provide
    Arbitrary<Integer> lastDigit() {
        return Arbitraries.integers().between(1, 9);
    }

    // ---- DB-backed ---------------------------------------------------------------------------------

    @Provide
    Arbitrary<List<List<CashLine>>> entryBatches() {
        return balancedLines().list().ofMinSize(1).ofMaxSize(5);
    }

    @Property(tries = 200)
    void T_DOM_01_postedEntriesKeepLedgerBalanced(@ForAll("entryBatches") List<List<CashLine>> batch,
                                                  @ForAll("reverseMask") List<Boolean> reverse) {
        UUID ns = LedgerDb.newNamespace();
        CashPostingService cash = Services.cash();
        ReversalService rev = Services.reversals();
        for (int i = 0; i < batch.size(); i++) {
            UUID id = cash.post(new CashEntry(ns, "GEN", TD, batch.get(i)));
            if (reverse.get(i % reverse.size())) rev.reverseCash(ns, id, "generated reversal");
        }
        for (Currency c : Currency.values()) {
            BigDecimal net = BigDecimal.ZERO;
            for (CashAccount a : CashAccount.values()) net = net.add(cash.balance(ns, a).getOrDefault(c, BigDecimal.ZERO));
            assertThat(net).as(c.name()).isEqualByComparingTo("0");
        }
    }

    @Provide
    Arbitrary<List<Boolean>> reverseMask() {
        return Arbitraries.of(true, false).list().ofMinSize(1).ofMaxSize(5);
    }

    record Move(int kind, Isin isin, long qty) {} // 0 buy-trade, 1 buy-settle, 2 sell-trade, 3 sell-settle

    static SecuritiesEntry entryFor(UUID ns, Move m) {
        Quantity q = Quantity.of(Long.toString(m.qty()));
        SecuritiesAccount[] dc = switch (m.kind()) {
            case 0 -> new SecuritiesAccount[] {SecuritiesAccount.PENDING, SecuritiesAccount.STREET};  // Dr S200 · Cr S900
            case 1 -> new SecuritiesAccount[] {SecuritiesAccount.CUSTODY, SecuritiesAccount.PENDING}; // Dr S100 · Cr S200
            case 2 -> new SecuritiesAccount[] {SecuritiesAccount.STREET, SecuritiesAccount.PENDING};  // Dr S900 · Cr S200
            default -> new SecuritiesAccount[] {SecuritiesAccount.PENDING, SecuritiesAccount.CUSTODY}; // Dr S200 · Cr S100
        };
        return new SecuritiesEntry(ns, "GEN_" + m.kind(), TD, List.of(
                new SecuritiesLine(dc[0], Side.D, m.isin(), q), new SecuritiesLine(dc[1], Side.C, m.isin(), q)));
    }

    @Provide
    Arbitrary<List<Move>> moves() {
        return Combinators.combine(Arbitraries.integers().between(0, 3), Arbitraries.of(ISINS),
                Arbitraries.longs().between(1, 1_000_000)).as(Move::new).list().ofMinSize(1).ofMaxSize(8);
    }

    @Property(tries = 200)
    void OM_03_projectionEqualsIncremental(@ForAll("moves") List<Move> moves, @ForAll("reverseMask") List<Boolean> reverse) {
        UUID ns = LedgerDb.newNamespace();
        SecuritiesPostingService sec = Services.securities();
        ReversalService rev = Services.reversals();
        for (int i = 0; i < moves.size(); i++) {
            UUID id = sec.post(entryFor(ns, moves.get(i)));
            if (reverse.get(i % reverse.size())) rev.reverseSecurities(ns, id, "generated reversal");
        }
        var recomputed = Services.positions().recompute(ns);
        for (Isin isin : ISINS) {
            assertThat(Services.positions().stored(ns, isin))
                    .as(isin.value()).isEqualTo(recomputed.getOrDefault(isin, com.secondline.ledger.positions.Position.ZERO));
        }
    }

    @Property(tries = 200)
    void T_DOM_05_reversalsNeverRemoveHistory(@ForAll("entryBatches") List<List<CashLine>> batch) throws Exception {
        UUID ns = LedgerDb.newNamespace();
        CashPostingService cash = Services.cash();
        ReversalService rev = Services.reversals();
        List<UUID> ids = new ArrayList<>();
        int originalLines = 0;
        for (List<CashLine> lines : batch) {
            ids.add(cash.post(new CashEntry(ns, "GEN", TD, lines)));
            originalLines += lines.size();
        }
        for (UUID id : ids) rev.reverseCash(ns, id, "generated reversal");
        assertThat(LedgerDb.query(LedgerDb.app(), "SELECT count(*) FROM ledger.journal_lines l JOIN ledger.journal_headers h"
                + " USING (ns, entry_id) WHERE ns = ? AND h.reverses_entry_id IS NULL", ns)).isEqualTo(Integer.toString(originalLines));
        for (UUID id : ids) {
            assertThat(cash.lines(ns, id)).hasSize(batch.get(ids.indexOf(id)).size());
        }
    }
}
