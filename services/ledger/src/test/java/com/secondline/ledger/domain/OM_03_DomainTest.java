package com.secondline.ledger.domain;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.secondline.ledger.LedgerException;
import java.math.BigDecimal;
import java.time.Instant;
import org.junit.jupiter.api.Test;

/** OM-03 §5 I2 ADR-016 (docs/domain.md precision): rejected, never rounded. */
class OM_03_DomainTest {

    static void invalid(Runnable r) {
        assertThatThrownBy(r::run).isInstanceOf(LedgerException.class)
                .extracting(e -> ((LedgerException) e).code()).isEqualTo("DOMAIN_INVALID");
    }

    @Test
    void OM_03_money_rejects_scale_above_minor_units() {
        invalid(() -> Money.of("1.5", Currency.JPY));
        invalid(() -> Money.of("0.001", Currency.USD));
        invalid(() -> Money.of("1e2", Currency.USD));
        assertThat(Money.of("10.10", Currency.USD).amount()).isEqualByComparingTo("10.1");
        assertThat(Money.of("100", Currency.JPY).amount()).isEqualByComparingTo("100");
        assertThat(Money.of("1000.50", Currency.EUR).amount()).isEqualByComparingTo("1000.5");
    }

    @Test
    void OM_03_money_rejects_zero_negative_and_float_text() {
        for (String bad : new String[] {"0", "0.00", "-1.00", "1.5E+1", " 1.00", "1,00", "+1", "01.00", "NaN", ""}) {
            invalid(() -> Money.of(bad, Currency.USD));
        }
        invalid(() -> new Money(null, Currency.USD));
        invalid(() -> new Money(BigDecimal.ONE, null));
    }

    @Test
    void OM_03_money_equality_ignores_trailing_zeros() {
        assertThat(Money.of("10.1", Currency.USD)).isEqualTo(Money.of("10.10", Currency.USD));
        assertThat(Money.of("10.1", Currency.USD).hashCode()).isEqualTo(Money.of("10.10", Currency.USD).hashCode());
        assertThat(Money.of("100", Currency.USD)).isEqualTo(new Money(new BigDecimal("1E+2"), Currency.USD));
        assertThat(Money.of("10.10", Currency.USD)).isNotEqualTo(Money.of("10.10", Currency.EUR));
    }

    @Test
    void OM_03_quantity_whole_and_positive() {
        assertThat(Quantity.of("100").units()).isEqualByComparingTo("100");
        assertThat(Quantity.of("100")).isEqualTo(new Quantity(new BigDecimal("100.000")));
        for (String bad : new String[] {"0", "-5", "10.5", "1e3", "abc"}) {
            invalid(() -> Quantity.of(bad));
        }
    }

    @Test
    void OM_03_price_scale_at_most_8() {
        assertThat(Price.of("12.34567891", Currency.USD).perShare()).isEqualByComparingTo("12.34567891");
        invalid(() -> Price.of("12.345678912", Currency.USD));
        invalid(() -> Price.of("0", Currency.USD));
    }

    @Test
    void OM_03_fx_rate_requires_source_and_id() {
        Instant t = Instant.parse("2026-10-30T16:00:00Z");
        FxRate r = new FxRate("fx_00000001", Currency.EUR, Currency.USD, new BigDecimal("1.0874500000"), "synthetic-ecb", t);
        assertThat(r.rate()).isEqualByComparingTo("1.08745");
        invalid(() -> new FxRate("", Currency.EUR, Currency.USD, BigDecimal.ONE, "src", t));
        invalid(() -> new FxRate("fx_00000001", Currency.EUR, Currency.USD, BigDecimal.ONE, " ", t));
        invalid(() -> new FxRate("fx_00000001", Currency.EUR, Currency.USD, BigDecimal.ONE, "src", null));
        invalid(() -> new FxRate("fx_00000001", Currency.EUR, Currency.EUR, BigDecimal.ONE, "src", t));
        invalid(() -> new FxRate("fx_00000001", Currency.EUR, Currency.USD, new BigDecimal("1.12345678901"), "src", t));
    }

    @Test
    void OM_03_currency_and_accounts_are_closed_sets() {
        assertThat(Currency.of("JPY").minorUnits()).isZero();
        assertThat(Currency.of("CHF").minorUnits()).isEqualTo(2);
        invalid(() -> Currency.of("usd"));
        invalid(() -> Currency.of("XXX"));
        assertThat(CashAccount.fromCode("1900")).isEqualTo(CashAccount.SUSPENSE);
        invalid(() -> CashAccount.fromCode("S100"));
        assertThat(SecuritiesAccount.fromCode("S900")).isEqualTo(SecuritiesAccount.STREET);
        invalid(() -> SecuritiesAccount.fromCode("1110"));
        assertThat(new Isin("US0000000001").value()).isEqualTo("US0000000001");
        invalid(() -> new Isin("us0000000001"));
    }
}
