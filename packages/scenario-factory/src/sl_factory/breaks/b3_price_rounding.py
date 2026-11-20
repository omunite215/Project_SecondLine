"""B3 price / rounding at the tolerance boundary (§5, ADR-016: adjust only if |diff| ≤ 1 minor unit × trades,
else escalate; docs/domain.md B3 row: 4100 vs 1210 for a pending trade).

Rounding (`within_tolerance`, `at_tolerance`): the booking system rounds the executed 8-dp price to 4 dp
(HALF_EVEN), so each booked consideration is off by ±1 minor unit; the broker confirm shows the full price.
`within_tolerance` mixes signs (+1, +1, −1 over 3 trades), `at_tolerance` hits |diff| = trades × 1 unit exactly.
Above tolerance (`above_tolerance`): the broker's price differs beyond 4-dp rounding (a price mismatch whose cash
size is one minor unit over tolerance) — a 4100 plug would balance and still be wrong (ADR-017 DG-3).
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal

from sl_factory.breaks import BOOKING_TRADE_DATE, BROKER_CONFIRM, BreakPlan, CashDelta
from sl_factory.lifecycle import PRICE_8DP, Simulator, TradeSim, gross, round_price, utc
from sl_factory.world import minor_unit

VARIANTS = ("within_tolerance", "at_tolerance", "above_tolerance")
TYPE = "B3_PRICE_ROUNDING"
_HALF_TICK = Decimal("0.00005")  # half of the 4th decimal


def _price_for(sim: Simulator, q: int, booked_price: Decimal, units: int) -> Decimal | None:
    """An 8-dp confirm price whose consideration is exactly `units` minor units away from the booked one."""
    target = gross(q, booked_price, sim.currency) + units * minor_unit(sim.currency)
    p = (target / q).quantize(PRICE_8DP, rounding=ROUND_HALF_EVEN)
    return p if p > 0 and gross(q, p, sim.currency) == target else None


def _trade(sim: Simulator, units: int, rounding: bool) -> TradeSim:
    unit, step = minor_unit(sim.currency), (100 if sim.currency == "JPY" else 10)
    for _ in range(1000):
        if rounding:  # |p − booked| < ½ tick needs q > (|u| + ½) · unit / ½ tick
            lo = int((abs(units) + 1) * unit / _HALF_TICK) + step
            q = sim.quantity(lo, lo * 20, step)
        else:  # |p − booked| ≥ ½ tick needs q ≤ (|u| − ½) · unit / ½ tick
            hi = int((abs(units) - Decimal("0.5")) * unit / _HALF_TICK)
            q = sim.rng.randrange(5, max(hi, 6))
        booked = sim.price()
        p = _price_for(sim, q, booked, units)
        if p is None or (round_price(p) == booked) != rounding:
            continue
        t = sim.pending_trade(quantity=q, price=booked)
        t.confirm_price = p
        return t
    raise RuntimeError("B3: no price met the tolerance construction")  # pragma: no cover


def _units(sim: Simulator, variant: str) -> list[int]:
    sign = sim.rng.choice((1, -1))
    if variant == "within_tolerance":
        per = [sign, sign, -sign]
        sim.rng.shuffle(per)
        return per  # |Σ| = 1 < 3 = tolerance
    if variant == "at_tolerance":
        return [sign] * sim.rng.randrange(1, 4)  # |Σ| = n = tolerance
    if variant == "above_tolerance":
        per = [sign] * sim.rng.randrange(1, 3)
        per[0] += sign
        return per  # |Σ| = n + 1
    raise ValueError(f"unknown B3 variant {variant!r}")


def build(sim: Simulator, variant: str) -> BreakPlan:
    ccy = sim.currency
    rounding = variant != "above_tolerance"
    trades, causes = [], []
    for units in _units(sim, variant):
        t = _trade(sim, units, rounding)
        kind, note = (
            ("booking_price_rounded", f"booked {t.booked_price}, executed {t.confirm_price}")
            if rounding
            else ("broker_price_differs", f"broker executed at {t.confirm_price}, booked {t.booked_price}")
        )
        causes.append(t.cause(sim.ids, kind, utc(t.trade_date, 14, 1), note))
        trades.append(t)
    diff = sum(
        (gross(t.quantity, t.confirm_price, ccy) - gross(t.quantity, t.booked_price, ccy) for t in trades), Decimal(0)
    )
    tol = minor_unit(ccy) * len(trades)
    if rounding:
        if abs(diff) > tol:  # construction invariant
            raise RuntimeError(f"B3 rounding diff {diff} above tolerance {tol}")  # pragma: no cover
        return BreakPlan(
            break_type=TYPE,
            variant=variant,
            trades=trades,
            cause_event_ids=causes,
            required=(BROKER_CONFIRM, BOOKING_TRADE_DATE),
            severity="LOW",
            root_cause="ROUNDING_DIFFERENCE",
            allowed=[("ADJUSTMENT", "ROUNDING_DIFFERENCE")],
            forbidden=[("CLASSIFY", "CUTOFF_TIMING"), ("BOOKING_CORRECTION", "QUANTITY_MISMATCH")],
            explanation=f"Rounding: booked prices were rounded to 4 dp; consideration differs by {diff} {ccy} over "
            f"{len(trades)} trade(s), within the {tol} {ccy} tolerance. Adjust 4100 vs 1210.",
            cash=[CashDelta(f"4100-{ccy}", ccy, diff), CashDelta(f"1210-{ccy}", ccy, -diff)],
        )
    return BreakPlan(
        break_type=TYPE,
        variant=variant,
        trades=trades,
        cause_event_ids=causes,
        required=(BROKER_CONFIRM, BOOKING_TRADE_DATE),
        severity="LOW",
        root_cause="PRICE_MISMATCH",
        allowed=[("ESCALATE", "PRICE_MISMATCH")],
        forbidden=[("ADJUSTMENT", "ROUNDING_DIFFERENCE"), ("CLASSIFY", "CUTOFF_TIMING")],
        explanation=f"Price mismatch: the broker price differs beyond 4-dp rounding; {diff} {ccy} over "
        f"{len(trades)} trade(s) is one minor unit above the {tol} {ccy} tolerance. Escalate; a 4100 "
        "plug balances and is still wrong.",
    )
