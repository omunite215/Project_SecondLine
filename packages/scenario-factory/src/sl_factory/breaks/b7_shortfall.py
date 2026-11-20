"""B7 settlement shortfall (§5, ADR-016: escalate, never fabricate a balancing entry — no 1900, no 4100; ADR-017
B7 row: no evidence required for escalation, should cite NOSTRO/SETTLEMENT_STATUS; DG-1, DG-3; KG-04 K4).

The bank posted settlement on the contractual date; the CSD reports the delivery FAILED for a shortfall. Reason
codes come from the curated ISO 20022 snapshot (KG-02, `verify: true` until SH-13) and are described in the
status text; the `status_code` field is left off so it can't mark the family. `cash` (MONY / CMON →
TREASURY), `securities` (LACK / CLAC → OPERATIONS).
"""

from __future__ import annotations

from functools import cache

from sl_factory import refdata
from sl_factory.breaks import SETTLEMENT_STATUS, BreakPlan, severity_for
from sl_factory.lifecycle import Simulator, gross, utc

VARIANTS = ("cash", "securities")
TYPE = "B7_SETTLEMENT_SHORTFALL"
_CODES = {"cash": ("MONY", "CMON"), "securities": ("LACK", "CLAC")}
_QUEUE = {"cash": "TREASURY", "securities": "OPERATIONS"}


@cache
def iso_codes() -> dict[str, str]:
    ref = max(r for r in refdata.refs() if r.startswith("iso20022@"))
    return {r["code"]: r["meaning"] for r in refdata.snapshot(ref, "settlement_codes.json")}


def build(sim: Simulator, variant: str) -> BreakPlan:
    if variant not in _CODES:
        raise ValueError(f"unknown B7 variant {variant!r}")
    t = sim.settled_trade(value_date=sim.as_of)
    t.events = [e for e in t.events if e.kind not in ("custodian_update", "settled")]
    code = sim.rng.choice(_CODES[variant])
    meaning = iso_codes()[code]
    t.ext_status, t.settled_quantity = "FAILED", 0
    # no status_code: only B7 would carry one (verified ISO codes for B8 failures don't exist yet), so the
    # field's presence would mark the family; the meaning is in the status text (leakage review)
    t.status_text = f"Settlement failed: {meaning.split(':')[0].lower()}."
    cause = t.cause(sim.ids, "settlement_shortfall", utc(sim.as_of, sim.market.cutoff_utc_hour - 1), meaning)
    g = gross(t.quantity, t.confirm_price, t.currency)
    return BreakPlan(
        break_type=TYPE,
        variant=variant,
        trades=[t],
        root_cause="CASH_SHORTFALL",
        allowed=[("ESCALATE", "CASH_SHORTFALL")],
        forbidden=[
            ("ADJUSTMENT", "ROUNDING_DIFFERENCE"),
            ("CLASSIFY", "CUTOFF_TIMING"),
            ("BOOKING_CORRECTION", "QUANTITY_MISMATCH"),
        ],
        required=(SETTLEMENT_STATUS,),
        cause_event_ids=[cause],
        explanation=f"Shortfall: delivery of {t.trade_id} failed ({code}: {meaning}). Escalate to "
        f"{_QUEUE[variant].lower()}; any balancing entry (1900, 4100) or timing classification is wrong.",
        severity=severity_for(g, t.currency),
        queue=_QUEUE[variant],
        balanced_but_false=True,
    )
