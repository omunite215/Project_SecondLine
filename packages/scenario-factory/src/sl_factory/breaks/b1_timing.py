"""B1 timing / cutoff (§5, ADR-016: classify, no posting; ADR-017: cite SETTLEMENT_STATUS + INTERNAL_BOOKING).

The bank posts settlement on the contractual value date. The custodian settles after its local statement cutoff
(variant `cutoff`) or the market is closed that day (`holiday`), so today's custodian and nostro statements lack
the movement. It settles next business day: a legitimate timing difference, not a booking error.
"""

from __future__ import annotations

from sl_factory.breaks import BOOKING_SETTLEMENT, SETTLEMENT_STATUS, BreakPlan
from sl_factory.lifecycle import Simulator, add_business_days, utc

VARIANTS = ("cutoff", "holiday")
TYPE = "B1_TIMING_CUTOFF"


def build(sim: Simulator, variant: str) -> BreakPlan:
    t = sim.settled_trade(value_date=sim.as_of)
    t.events = [e for e in t.events if e.kind not in ("custodian_update", "settled")]
    nxt = add_business_days(sim.as_of, 1)
    cut = sim.market.cutoff_utc_hour
    if variant == "cutoff":
        late = sim.rng.randrange(5, 90)
        cause = t.cause(
            sim.ids,
            "custodian_cutoff_missed",
            utc(sim.as_of, cut + late // 60, late % 60),
            f"delivery matched {late} min after the {sim.market.name} 16:00 cutoff",
        )
        t.cutoff_time = utc(sim.as_of, cut)
        t.status_text = f"Matched after the {sim.market.name} cutoff; settles {nxt}."
        why = f"delivery matched after the {sim.market.name} cutoff on {sim.as_of}"
    elif variant == "holiday":
        cause = t.cause(sim.ids, "custodian_market_holiday", utc(sim.as_of, 0), f"{sim.market.name} closed")
        t.status_text = f"{sim.market.name} market closed {sim.as_of}; settles {nxt}."
        why = f"the {sim.market.name} market was closed on {sim.as_of}"
    else:
        raise ValueError(f"unknown B1 variant {variant!r}")
    t.ext_status, t.status_settle_date, t.settled_quantity = "MATCHED", nxt, 0
    return BreakPlan(
        break_type=TYPE,
        variant=variant,
        trades=[t],
        root_cause="CUTOFF_TIMING",
        allowed=[("CLASSIFY", "CUTOFF_TIMING")],
        forbidden=[
            ("BOOKING_CORRECTION", "QUANTITY_MISMATCH"),
            ("BOOKING_CORRECTION", "MISSING_TRADE"),
            ("ADJUSTMENT", "ROUNDING_DIFFERENCE"),
        ],
        required=(SETTLEMENT_STATUS, BOOKING_SETTLEMENT),
        cause_event_ids=[cause],
        explanation=f"Timing only: the bank booked settlement of {t.trade_id} on {sim.as_of}, but {why}; "
        f"the custodian settles it on {nxt}. Classify as cutoff timing; any posting is wrong.",
        severity="LOW",
    )
