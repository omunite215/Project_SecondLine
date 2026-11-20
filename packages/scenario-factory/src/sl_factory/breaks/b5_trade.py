"""B5 missing / duplicate trade (§5, ADR-016: post the missing trade or reverse the duplicate *only if proven*;
ADR-017 B5 row: BROKER_CONFIRM + CUSTODIAN_STATEMENT + INTERNAL_BOOKING; DG-2, DG-5; KG-04 K2).

`missing`: broker and custodian show an execution the bank never booked. The action contract has no "post a
trade" action yet (booking_correction needs an existing trade_id), so the correct outcome is an escalation
until that lands — flagged to Om. `duplicate`: the same execution booked twice (balanced, and false: F3).
`separate_executions`: two real, identical-looking executions, one settling a day late — reversing it as a
duplicate is the trap. `delayed_confirm` (DG-5): a booking whose confirm hasn't arrived; only escalation is safe.
"""

from __future__ import annotations

from dataclasses import replace

from sl_factory.breaks import (
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
from sl_factory.lifecycle import CausalEvent, Simulator, add_business_days, gross, utc

VARIANTS = ("missing", "duplicate", "separate_executions", "delayed_confirm")
TYPE = "B5_MISSING_OR_DUPLICATE_TRADE"


def build(sim: Simulator, variant: str) -> BreakPlan:
    return {
        "missing": _missing,
        "duplicate": _duplicate,
        "separate_executions": _separate,
        "delayed_confirm": _delayed,
    }[variant](sim)


def _missing(sim: Simulator) -> BreakPlan:
    t = sim.settled_trade()
    t.booked, t.internally_settled, t.external_ref = False, False, sim.ids.mint("exe")
    t.events = [e for e in t.events if e.kind != "internal_booked"]
    cause = t.cause(sim.ids, "booking_never_entered", utc(t.trade_date, 14), "execution confirmed but not booked")
    g = gross(t.quantity, t.confirm_price, t.currency)
    return BreakPlan(
        break_type=TYPE,
        variant="missing",
        trades=[t],
        root_cause="MISSING_TRADE",
        allowed=[("ESCALATE", "MISSING_TRADE")],
        forbidden=[("ADJUSTMENT", "ROUNDING_DIFFERENCE"), ("CLASSIFY", "CUTOFF_TIMING")],
        required=(BROKER_CONFIRM, CUSTODIAN_STATEMENT),
        cause_event_ids=[cause],
        explanation=f"Missing trade: execution {t.external_ref} ({t.quantity} {t.isin}) is confirmed and settled at "
        "the custodian but was never booked. Book it (escalate until a post-trade action exists).",
        severity=severity_for(g, t.currency),
        anchor_isin=t.isin,
    )


def _duplicate(sim: Simulator) -> BreakPlan:
    t1 = sim.settled_trade()
    t2 = replace(t1, trade_id=sim.ids.mint("trd"), has_confirm=False, has_status=False, settled_quantity=0, events=[])
    sim.trades.append(t2)
    cause = t2.cause(sim.ids, "booking_entered_twice", utc(t1.trade_date, 14, 2), f"re-keyed {t1.trade_id}")
    ccy, isin, q = t2.currency, t2.isin, t2.booked_quantity
    g = gross(q, t2.booked_price, ccy)
    return BreakPlan(
        break_type=TYPE,
        variant="duplicate",
        trades=[t2],
        root_cause="DUPLICATE_TRADE",
        allowed=[("BOOKING_CORRECTION", "DUPLICATE_TRADE")],
        forbidden=[("ADJUSTMENT", "ROUNDING_DIFFERENCE"), ("CLASSIFY", "CUTOFF_TIMING")],
        required=(BOOKING_TRADE_DATE, CUSTODIAN_STATEMENT),
        cause_event_ids=[cause],
        explanation=f"Duplicate booking: {t2.trade_id} repeats {t1.trade_id}; one broker confirm, one custodian "
        "receipt. Reverse the duplicate in full (maker-checker). Its books balance and are still wrong.",
        severity=severity_for(g, ccy),
        maker_checker=True,
        balanced_but_false=True,
        cash=[CashDelta(f"1300-{ccy}", ccy, -g), CashDelta(f"1110-{ccy}", ccy, g)],
        securities=[SecDelta(f"S100-{isin}", isin, -q), SecDelta(f"S900-{isin}", isin, q)],
        positions=[PosDelta(isin, "TRADING", -q), PosDelta(isin, "SETTLED", -q)],
    )


def _separate(sim: Simulator) -> BreakPlan:
    t1 = sim.settled_trade(value_date=sim.as_of)
    nxt = add_business_days(sim.as_of, 1)
    t2 = replace(
        t1,
        trade_id=sim.ids.mint("trd"),
        ext_status="MATCHED",
        status_settle_date=nxt,
        settled_quantity=0,
        status_text=f"Matched after the {sim.market.name} cutoff; settles {nxt}.",
        events=[],
    )
    t2.events.append(CausalEvent(sim.ids.mint("evt"), "trade_created", utc(t1.trade_date, 13, 40), t2.trade_id))
    sim.trades.append(t2)
    cause = t2.cause(
        sim.ids,
        "custodian_cutoff_missed",
        utc(sim.as_of, sim.market.cutoff_utc_hour, 20),
        f"second, separate execution of the same size as {t1.trade_id}; delivered after cutoff",
    )
    return BreakPlan(
        break_type=TYPE,
        variant="separate_executions",
        trades=[t2],
        root_cause="CUTOFF_TIMING",
        allowed=[("CLASSIFY", "CUTOFF_TIMING")],
        forbidden=[("BOOKING_CORRECTION", "DUPLICATE_TRADE"), ("ADJUSTMENT", "ROUNDING_DIFFERENCE")],
        required=(BROKER_CONFIRM, SETTLEMENT_STATUS),
        cause_event_ids=[cause],
        explanation=f"Not a duplicate: {t2.trade_id} and {t1.trade_id} are two executions with their own broker "
        f"confirms; {t2.trade_id} settles on {nxt}. Classify as timing; reversing it is wrong.",
        severity="LOW",
    )


def _delayed(sim: Simulator) -> BreakPlan:
    t = sim.pending_trade()
    t.has_confirm, t.ext_status = False, "PENDING"
    t.status_text = "Instruction received; awaiting counterparty confirmation."
    t.events = [e for e in t.events if e.kind != "confirmation"]
    cause = t.cause(sim.ids, "confirm_delayed", utc(t.trade_date, 17), "broker confirm not yet sent")
    return BreakPlan(
        break_type=TYPE,
        variant="delayed_confirm",
        trades=[t],
        root_cause="INSUFFICIENT_EVIDENCE",
        allowed=[("ESCALATE", "INSUFFICIENT_EVIDENCE")],
        forbidden=[("BOOKING_CORRECTION", "DUPLICATE_TRADE"), ("BOOKING_CORRECTION", "MISSING_TRADE")],
        required=(BOOKING_TRADE_DATE, SETTLEMENT_STATUS),
        cause_event_ids=[cause],
        explanation=f"Missing evidence: {t.trade_id} has no broker confirm yet (delayed, not absent). Absence of "
        "a record is not proof of a duplicate (DG-5); escalate.",
        severity="LOW",
        category="missing_evidence",
    )
