"""Trade lifecycle simulator: causal events FIRST, then the facts every record is rendered from (KG-03, §5).

trade_created → internal_booked → confirmation → settlement_instruction → custodian_update → settled / partial /
pending. A `TradeSim` keeps the true facts (what was executed and what the custodian did) apart from the bank's
own records (what was booked), so every break is a difference between the two that has a cause event.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

from sl_factory.rng import IdMinter
from sl_factory.world import MARKETS, MINOR_UNITS, PRICE_RANGE, Counterparty, Instrument, World

PRICE_4DP = Decimal("0.0001")
PRICE_8DP = Decimal("0.00000001")


# ---- dates, times and money ----------------------------------------------------------------------------------
def add_business_days(d: str, n: int) -> str:
    day = date.fromisoformat(d)
    step = 1 if n >= 0 else -1
    left = abs(n)
    while left:
        day += timedelta(days=step)
        if day.weekday() < 5:
            left -= 1
    return day.isoformat()


def utc(d: str, hour: int, minute: int = 0) -> str:
    return f"{d}T{hour:02d}:{minute:02d}:00Z"


def money(amount: Decimal, currency: str) -> Decimal:
    """Round once at the posting boundary: HALF_EVEN to ISO 4217 minor units (ADR-016)."""
    return amount.quantize(Decimal(1).scaleb(-MINOR_UNITS[currency]), rounding=ROUND_HALF_EVEN)


def gross(quantity: int, price: Decimal, currency: str) -> Decimal:
    return money(price * quantity, currency)


def dec_str(d: Decimal) -> str:
    s = format(d, "f")
    return "0" if s in ("-0", "0") or Decimal(s) == 0 else s


def round_price(p: Decimal) -> Decimal:
    """The booking system's 4-dp price (HALF_EVEN): the B3 rounding cause."""
    return p.quantize(PRICE_4DP, rounding=ROUND_HALF_EVEN)


# ---- causal events and trade facts ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CausalEvent:
    event_id: str
    kind: str
    at: str
    trade_id: str
    note: str = ""


@dataclass
class TradeSim:
    trade_id: str
    instrument: Instrument
    counterparty: Counterparty
    quantity: int  # executed (true; what the broker confirms)
    confirm_price: Decimal  # executed price (true; up to 8 dp)
    booked_quantity: int  # bank's booking
    booked_price: Decimal  # bank's booking (4 dp)
    trade_date: str
    value_date: str  # contractual settlement date
    ext_status: str  # custodian/CSD view: SETTLED | MATCHED | PARTIALLY_SETTLED
    status_settle_date: str  # actual (or expected) custodian settlement date
    settled_quantity: int  # quantity the custodian delivered by as_of
    internally_settled: bool  # the bank posted settlement entries (contractual-date assumption)
    cutoff_time: str | None = None
    status_text: str = ""
    events: list[CausalEvent] = field(default_factory=list)
    # KG-04: which records exist at all (B5 missing / duplicate / delayed confirm; B7/B8 failures)
    booked: bool = True  # the bank has a booking (False: B5 missing trade)
    has_confirm: bool = True  # the broker confirm has arrived (False: duplicate booking, delayed confirm)
    has_status: bool = True  # the CSD knows the trade (False: a duplicate booking never instructed)
    external_ref: str | None = None  # broker/CSD reference when the bank has no booking (B5 missing)
    status_code: str | None = None  # ISO 20022 pending/failing reason (B7), from refdata

    @property
    def ref(self) -> str:
        """The trade reference external records carry."""
        return self.external_ref or self.trade_id

    @property
    def currency(self) -> str:
        return self.instrument.currency

    @property
    def isin(self) -> str:
        return self.instrument.isin

    def cause(self, ids: IdMinter, kind: str, at: str, note: str) -> str:
        ev = CausalEvent(ids.mint("evt"), kind, at, self.trade_id, note)
        self.events.append(ev)
        return ev.event_id


class Simulator:
    """Builds clean trades for one scenario; break generators then change facts and record the cause event."""

    def __init__(self, rng: random.Random, ids: IdMinter, world: World, currency: str, as_of: str) -> None:
        self.rng, self.ids, self.world, self.currency, self.as_of = rng, ids, world, currency, as_of
        self.market = MARKETS[currency]
        self.trades: list[TradeSim] = []
        self.extras: list[Any] = []  # render.Extra facts beyond trades (FX revaluation, CA, SSI); KG-04
        self.events: list[tuple[str, str, str, str]] = []  # scenario-level causes: (event_id, kind, at, note)

    # draws
    def quantity(self, lo: int, hi: int, step: int = 10) -> int:
        return self.rng.randrange(lo // step, hi // step + 1) * step

    def price(self) -> Decimal:
        lo, hi = PRICE_RANGE[self.currency]
        return (Decimal(self.rng.randrange(lo * 10_000, hi * 10_000)) * PRICE_4DP).quantize(PRICE_4DP)

    def executed_price(self, q: int, booked: Decimal) -> Decimal:
        """An 8-dp executed price that the 4-dp booking rounds to with the same consideration: every confirm
        carries 8 dp, so the precision itself never marks a break (leakage review, KG-03)."""
        for _ in range(20):
            p = booked + Decimal(self.rng.randrange(-4999, 5000)) * PRICE_8DP
            if p > 0 and round_price(p) == booked and gross(q, p, self.currency) == gross(q, booked, self.currency):
                return p
        return booked.quantize(PRICE_8DP)

    def cutoff(self, d: str) -> str:
        return utc(d, self.market.cutoff_utc_hour)

    def default_quantity(self) -> int:
        return self.quantity(20_000, 120_000, 100) if self.currency == "JPY" else self.quantity(100, 5_000)

    def _events(self, t: TradeSim, settled: bool) -> None:
        cut = self.market.cutoff_utc_hour
        for kind, d, h in (
            ("trade_created", t.trade_date, 13),
            ("internal_booked", t.trade_date, 14),
            ("confirmation", t.trade_date, 17),
            ("settlement_instruction", t.trade_date, 18),
        ):
            t.events.append(CausalEvent(self.ids.mint("evt"), kind, utc(d, h), t.trade_id))
        if settled:
            t.events.append(
                CausalEvent(self.ids.mint("evt"), "custodian_update", utc(t.value_date, cut - 2), t.trade_id)
            )
            t.events.append(CausalEvent(self.ids.mint("evt"), "settled", utc(t.value_date, cut - 2, 5), t.trade_id))

    def settled_trade(self, *, value_date: str | None = None, quantity: int | None = None) -> TradeSim:
        """A trade the custodian settled on its value date, booked and settled internally: no difference."""
        vd = value_date or add_business_days(self.as_of, -self.rng.randrange(0, 3))
        q = quantity or self.default_quantity()
        p = self.price()
        ins = self.rng.choice(self.world.instruments_in(self.currency))
        t = TradeSim(
            self.ids.mint("trd"),
            ins,
            self.rng.choice(self.world.counterparties),
            q,
            self.executed_price(q, p),
            q,
            p,
            add_business_days(vd, -2),
            vd,
            "SETTLED",
            vd,
            q,
            True,
            cutoff_time=self.cutoff(vd),
            status_text=f"Settled {vd}.",
        )
        self._events(t, settled=True)
        self.trades.append(t)
        return t

    def pending_trade(
        self, *, quantity: int | None = None, price: Decimal | None = None, instrument: Instrument | None = None
    ) -> TradeSim:
        """Traded today, matched, settling T+2: trade-date entries only."""
        q = quantity or self.default_quantity()
        p = price or self.price()
        vd = add_business_days(self.as_of, 2)
        ins = instrument or self.rng.choice(self.world.instruments_in(self.currency))
        t = TradeSim(
            self.ids.mint("trd"),
            ins,
            self.rng.choice(self.world.counterparties),
            q,
            self.executed_price(q, p),
            q,
            p,
            self.as_of,
            vd,
            "MATCHED",
            vd,
            0,
            False,
            cutoff_time=self.cutoff(vd),
            status_text=f"Matched; settles {vd}.",
        )
        self._events(t, settled=False)
        self.trades.append(t)
        return t
