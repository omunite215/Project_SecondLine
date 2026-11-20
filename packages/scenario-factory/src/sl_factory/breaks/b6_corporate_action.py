"""B6 corporate action (§5, ADR-016 B6 row: S100 × ratio vs S900, whole shares; ADR-017 B6 row: cite CA_NOTICE +
CUSTODIAN_STATEMENT + INTERNAL_BOOKING; ADR-014: CORPORATE_ACTION always needs approval; KG-04 K3).

A forward split on a held ISIN, effective today. The custodian applies the notice; the bank `wrong_ex_date`
(didn't apply it yet) or `wrong_entitlement` (applied another ratio). Holdings are kept to multiples of the
ratio's denominator, so entitlements are whole (cash in lieu for fractions: KG-04 as-built note).
`CorporateAction(bank_ratio=ratio)` is the correctly processed background version (no break).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sl_factory.breaks import (
    BOOKING_CA,
    BOOKING_TRADE_DATE,
    CA_NOTICE,
    CUSTODIAN_STATEMENT,
    BreakPlan,
    PosDelta,
    SecDelta,
)
from sl_factory.lifecycle import Simulator, TradeSim, add_business_days, utc
from sl_factory.render import RecordIds, Records, evidence, movement
from sl_factory.rng import IdMinter

VARIANTS = ("wrong_ex_date", "wrong_entitlement")
TYPE = "B6_CORPORATE_ACTION"
RATIOS = ((2, 1), (3, 2), (5, 4))


@dataclass
class CorporateAction:
    isin: str
    currency: str
    ratio: tuple[int, int]
    ex_date: str
    trades: list[TradeSim]  # the scenario's trade list; holdings are read at render time
    bank_ratio: tuple[int, int] | None  # what the bank applied (None: not applied)
    holdings: dict[str, int] = field(default_factory=dict)
    bank_new: int = 0
    true_new: int = 0

    def render(self, ids: IdMinter, rec: RecordIds, as_of: str) -> Records:
        out = Records()
        held = sum(t.settled_quantity for t in self.trades if t.isin == self.isin)
        booked = sum(t.booked_quantity for t in self.trades if t.isin == self.isin and t.internally_settled)
        n, d = self.ratio
        self.true_new = held * n // d
        self.holdings = {self.isin: self.true_new - held}
        out.evidence.append(
            e := evidence(
                ids,
                "CA_NOTICE",
                "ca_sim",
                utc(add_business_days(self.ex_date, -5), 9),
                {
                    "isin": self.isin,
                    "event_type": "SPLF",
                    "ratio_new": str(n),
                    "ratio_old": str(d),
                    "ex_date": self.ex_date,
                    "record_date": add_business_days(self.ex_date, -1),
                    "pay_date": self.ex_date,
                    "currency": self.currency,
                },
                f"Forward split {n}-for-{d} on {self.isin}, ex-date {self.ex_date}.",
            )
        )
        rec.named["ca_notice"] = e["record_id"]
        self.bank_new = booked
        if self.bank_ratio:
            bn, bd = self.bank_ratio
            self.bank_new = booked * bn // bd
            if self.bank_new != booked:
                at = utc(self.ex_date, 6)
                m = movement(ids, at, self.isin, "S100", "DR", self.bank_new - booked)
                rec.named["ca_entry"] = m["movement_id"]
                out.movements += [m, movement(ids, at, self.isin, "S900", "CR", self.bank_new - booked)]
        return out


def _holding(sim: Simulator) -> tuple[str, list[TradeSim]]:
    used = {t.isin for t in sim.trades} | sim.reserved
    free = [i for i in sim.world.instruments_in(sim.currency) if i.isin not in used]
    if not free:
        raise ValueError("B6: no unheld ISIN left for the corporate action")  # redraw
    ins = sim.rng.choice(free)
    sim.reserved.add(ins.isin)
    step = 100 if sim.currency == "JPY" else 20  # multiple of every ratio denominator (1, 2, 4)
    lo, hi = (20_000, 100_000) if sim.currency == "JPY" else (200, 4_000)
    trades = [
        sim.settled_trade(
            value_date=add_business_days(sim.as_of, -sim.rng.randrange(2, 6)),
            quantity=sim.quantity(lo, hi, step),
            instrument=ins,
        )
        for _ in range(sim.rng.randrange(1, 3))
    ]
    return ins.isin, trades


def background(sim: Simulator) -> CorporateAction:
    isin, _ = _holding(sim)
    ratio = sim.rng.choice(RATIOS)
    return CorporateAction(isin, sim.currency, ratio, sim.as_of, sim.trades, bank_ratio=ratio)


def build(sim: Simulator, variant: str) -> BreakPlan:
    isin, holding = _holding(sim)
    ratio = sim.rng.choice(RATIOS)
    if variant == "wrong_ex_date":
        bank: tuple[int, int] | None = None
        why = "did not apply it on the ex-date"
    elif variant == "wrong_entitlement":
        bank = sim.rng.choice([r for r in RATIOS if r != ratio])
        why = f"applied {bank[0]}-for-{bank[1]} instead of {ratio[0]}-for-{ratio[1]}"
    else:
        raise ValueError(f"unknown B6 variant {variant!r}")
    x = CorporateAction(isin, sim.currency, ratio, sim.as_of, sim.trades, bank_ratio=bank)
    sim.extras.append(x)
    held = sum(t.quantity for t in holding)
    true_new = held * ratio[0] // ratio[1]
    bank_new = held * bank[0] // bank[1] if bank else held
    dq = true_new - bank_new
    cause = sim.ids.mint("evt")
    sim.events.append((cause, "corporate_action_misprocessed", utc(sim.as_of, 6), f"bank {why}"))
    return BreakPlan(
        break_type=TYPE,
        variant=variant,
        trades=holding,
        root_cause="CORPORATE_ACTION_SPLIT",
        allowed=[("CORPORATE_ACTION", "CORPORATE_ACTION_SPLIT")],
        forbidden=[("BOOKING_CORRECTION", "QUANTITY_MISMATCH"), ("ADJUSTMENT", "ROUNDING_DIFFERENCE")],
        required=(CUSTODIAN_STATEMENT, BOOKING_TRADE_DATE),
        named_required=(CA_NOTICE, BOOKING_CA) if bank else (CA_NOTICE,),
        cause_event_ids=[cause],
        explanation=f"Corporate action: {ratio[0]}-for-{ratio[1]} split on {isin} effective {sim.as_of}; the bank "
        f"{why}. Process the split per the notice: {dq:+} shares (maker-checker).",
        severity="MEDIUM",
        maker_checker=True,
        anchor_isin=isin,
        securities=[SecDelta(f"S100-{isin}", isin, dq), SecDelta(f"S900-{isin}", isin, -dq)],
        positions=[PosDelta(isin, "TRADING", dq), PosDelta(isin, "SETTLED", dq)],
    )
