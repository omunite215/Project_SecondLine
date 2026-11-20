"""B2 quantity mismatch (§5, ADR-016: reverse + rebook at the evidenced quantity, maker-checker; ADR-017).

`booking_error`: the bank keyed the wrong quantity; broker and custodian show the executed quantity.
`partial_settlement` (plan D2): the booking is right, the custodian delivered only part of it — it looks like a
booking error on the position report, but a booking correction would be wrong.
"""

from __future__ import annotations

from sl_factory.breaks import (
    BOOKING_SETTLEMENT,
    BOOKING_TRADE_DATE,
    BROKER_CONFIRM,
    CUSTODIAN_STATEMENT,
    SETTLEMENT_STATUS,
    BreakPlan,
    CashDelta,
    PosDelta,
    SecDelta,
    severity_for,
)
from sl_factory.lifecycle import Simulator, gross, utc

VARIANTS = ("booking_error", "partial_settlement")
TYPE = "B2_QUANTITY_MISMATCH"


def _fat_finger(q: int, pick: int, digit: int) -> int:
    """A keying error on q: an extra/missing zero, transposed digits, or a wrong digit."""
    s = str(q)
    candidates = [q * 10, q // 10 if q % 10 == 0 else q + 9 * 10 ** (len(s) - 1)]
    if len(s) >= 2 and s[0] != s[1]:
        candidates.append(int(s[1] + s[0] + s[2:]))
    candidates.append(q + digit * 10 ** max(len(s) - 2, 0))
    out = candidates[pick % len(candidates)]
    return out if out > 0 and out != q else q + 10


def build(sim: Simulator, variant: str) -> BreakPlan:
    if variant == "booking_error":
        return _booking_error(sim)
    if variant == "partial_settlement":
        return _partial(sim)
    raise ValueError(f"unknown B2 variant {variant!r}")


def _booking_error(sim: Simulator) -> BreakPlan:
    t = sim.settled_trade()
    booked = _fat_finger(t.quantity, sim.rng.randrange(4), sim.rng.randrange(1, 9))
    t.booked_quantity = booked
    cause = t.cause(
        sim.ids,
        "booking_quantity_keyed",
        utc(t.trade_date, 14, 1),
        f"booked {booked} instead of the executed {t.quantity}",
    )
    dq = t.quantity - booked
    d = gross(t.quantity, t.confirm_price, t.currency) - gross(booked, t.booked_price, t.currency)
    ccy, isin = t.currency, t.isin
    return BreakPlan(
        break_type=TYPE,
        variant="booking_error",
        trades=[t],
        root_cause="QUANTITY_MISMATCH",
        allowed=[("BOOKING_CORRECTION", "QUANTITY_MISMATCH")],
        forbidden=[
            ("ADJUSTMENT", "ROUNDING_DIFFERENCE"),
            ("CLASSIFY", "CUTOFF_TIMING"),
            ("CLASSIFY", "PARTIAL_SETTLEMENT"),
        ],
        required=(BROKER_CONFIRM, BOOKING_TRADE_DATE, BOOKING_SETTLEMENT, CUSTODIAN_STATEMENT),
        cause_event_ids=[cause],
        explanation=f"Booking error: {t.trade_id} was booked as {booked} shares; the broker confirm and the "
        f"custodian show the executed {t.quantity}. Reverse and rebook at {t.quantity} with maker-checker.",
        severity=severity_for(d, ccy),
        maker_checker=True,
        # Net of reversal + rebook for a settled trade (ADR-016 B2 row): cost and nostro, custody and street.
        cash=[CashDelta(f"1300-{ccy}", ccy, d), CashDelta(f"1110-{ccy}", ccy, -d)],
        securities=[SecDelta(f"S100-{isin}", isin, dq), SecDelta(f"S900-{isin}", isin, -dq)],
        positions=[PosDelta(isin, "TRADING", dq), PosDelta(isin, "SETTLED", dq)],
    )


def _partial(sim: Simulator) -> BreakPlan:
    t = sim.settled_trade(value_date=sim.as_of)
    t.events = [e for e in t.events if e.kind != "settled"]
    part = max(1, round(t.quantity * sim.rng.randrange(20, 81) / 100))
    if sim.currency != "JPY" and part >= 10:
        part -= part % 10
    t.ext_status, t.settled_quantity = "PARTIALLY_SETTLED", part
    t.status_text = f"Partially settled {part} of {t.quantity}; remainder pending delivery."
    cause = t.cause(
        sim.ids,
        "custodian_partial_delivery",
        utc(sim.as_of, sim.market.cutoff_utc_hour - 2),
        f"counterparty delivered {part} of {t.quantity}",
    )
    return BreakPlan(
        break_type=TYPE,
        variant="partial_settlement",
        trades=[t],
        root_cause="PARTIAL_SETTLEMENT",
        allowed=[("CLASSIFY", "PARTIAL_SETTLEMENT"), ("ESCALATE", "PARTIAL_SETTLEMENT")],
        forbidden=[("BOOKING_CORRECTION", "QUANTITY_MISMATCH"), ("ADJUSTMENT", "ROUNDING_DIFFERENCE")],
        required=(SETTLEMENT_STATUS, BROKER_CONFIRM, CUSTODIAN_STATEMENT),
        cause_event_ids=[cause],
        explanation=f"Partial settlement, not a booking error: {t.trade_id} is correctly booked at {t.quantity} "
        f"(broker confirm agrees); the custodian delivered {part}. No booking correction.",
        severity="MEDIUM",
    )
