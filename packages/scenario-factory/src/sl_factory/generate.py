"""One scenario: seed → world → lifecycle → cause → visible records → recon → truth + manifest (KG-03).

Order matters and is fixed: ids, world, picks, lifecycle. Same (split, index, args) ⇒ same bytes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from sl_factory.breaks import (
    BOOKING_SETTLEMENT,
    BOOKING_TRADE_DATE,
    BROKER_CONFIRM,
    CUSTODIAN_STATEMENT,
    SETTLEMENT_STATUS,
    BreakPlan,
    b1_timing,
    b2_quantity,
    b3_price_rounding,
)
from sl_factory.canonical import sha256_ref
from sl_factory.lifecycle import Simulator, add_business_days, dec_str
from sl_factory.render import RecordIds, reconcile, render
from sl_factory.rng import IdMinter, Streams, derive_seed, make_canary
from sl_factory.version import GENERATOR_VERSION, SOURCE_REF
from sl_factory.world import CURRENCIES, build_world

JSON = dict[str, Any]
AUTO = "auto"
VARIANTS: dict[str, tuple[str, ...]] = {
    b1_timing.TYPE: b1_timing.VARIANTS,
    b2_quantity.TYPE: b2_quantity.VARIANTS,
    b3_price_rounding.TYPE: b3_price_rounding.VARIANTS,
}
_BUILDERS: dict[str, Callable[[Simulator, str], BreakPlan]] = {
    b1_timing.TYPE: b1_timing.build,
    b2_quantity.TYPE: b2_quantity.build,
    b3_price_rounding.TYPE: b3_price_rounding.build,
}
_FIRST_AS_OF = "2026-01-05"  # a Monday; as-of dates are business days after it


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    bundle: JSON  # agent-visible
    truth: JSON | None  # privileged; None for a clean (no-break) world
    manifest: JSON  # agent-visible
    explanation: JSON | None  # privileged sidecar (plan D1)


def _required_ids(plan: BreakPlan, rec: RecordIds) -> list[str]:
    out: set[str] = set()
    for t in plan.trades:
        for role in plan.required:
            if role == SETTLEMENT_STATUS:
                out.add(rec.status[t.trade_id])
            elif role == BROKER_CONFIRM:
                out.add(rec.confirm[t.trade_id])
            elif role == CUSTODIAN_STATEMENT:
                out.add(rec.custodian[t.isin])
            elif role == BOOKING_TRADE_DATE:
                out.add(rec.trade_entry[t.trade_id])
            elif role == BOOKING_SETTLEMENT:
                out.add(rec.settle_entry[t.trade_id])
            else:  # pragma: no cover
                raise ValueError(role)
    return sorted(out)


def _break_truth(plan: BreakPlan, break_id: str, rec: RecordIds) -> JSON:
    return {
        "break_id": break_id,
        "break_type": plan.break_type,
        "root_cause": plan.root_cause,
        "causal_event_ids": plan.cause_event_ids,
        "allowed_outcomes": [{"type": a, "reason_code": r} for a, r in plan.allowed],
        "forbidden_outcomes": [{"type": a, "reason_code": r} for a, r in plan.forbidden],
        "required_evidence_ids": _required_ids(plan, rec),
        "approval_requirements": {"maker_checker": plan.maker_checker},
        "expected_state_delta": {
            "cash": [{"account": c.account, "currency": c.currency, "delta": dec_str(c.delta)} for c in plan.cash],
            "securities": [{"account": s.account, "isin": s.isin, "delta": str(s.delta)} for s in plan.securities],
            "positions": [{"isin": p.isin, "basis": p.basis, "delta": str(p.delta)} for p in plan.positions],
        },
        "escalation_if_insufficient_evidence": {"queue": plan.queue},
        "severity": plan.severity,
    }


def generate_scenario(
    split: str, index: int, break_type: str | None = AUTO, variant: str | None = None, currency: str | None = None
) -> Scenario:
    seed = derive_seed(split, index)
    streams = Streams(seed)
    ids = IdMinter(streams.stream("ids"))
    scenario_id = ids.mint("scn")
    world = build_world(streams, ids)
    pick = streams.stream("pick")
    if break_type == AUTO:
        break_type = tuple(VARIANTS)[index % len(VARIANTS)]
    if break_type is not None and variant is None:
        variant = pick.choice(VARIANTS[break_type])
    ccy = currency or pick.choice(CURRENCIES)
    as_of = add_business_days(_FIRST_AS_OF, pick.randrange(0, 250))
    sim = Simulator(streams.stream("lifecycle"), ids, world, ccy, as_of)
    for _ in range(pick.randrange(1, 5)):
        sim.settled_trade()  # background trades that reconcile cleanly
    plan = _BUILDERS[break_type](sim, variant or "") if break_type else None
    for _ in range(pick.randrange(0, 4)):
        sim.pending_trade()

    bundle, rec = render(sim.trades, ids, scenario_id, as_of)
    bundle["breaks"] = reconcile(bundle, ids)
    manifest: JSON = {
        "scenario_id": scenario_id,
        "schema_version": "1.0",
        "snapshot_hash": sha256_ref(bundle),
        "source_snapshot_refs": [SOURCE_REF],
        "initial_state_ref": f"snapshot/{scenario_id}",
    }
    if plan is None:
        if bundle["breaks"]:
            raise RuntimeError(f"clean world {scenario_id} produced breaks")  # pragma: no cover
        return Scenario(scenario_id, bundle, None, manifest, None)

    (found,) = bundle["breaks"]  # one cause ⇒ recon must find exactly its trades
    if set(found["trade_ids"]) != {t.trade_id for t in plan.trades}:
        raise RuntimeError(f"{scenario_id}: recon found {found['trade_ids']}, cause is on others")  # pragma: no cover
    truth: JSON = {
        "truth_version": "1.0",
        "scenario_id": scenario_id,
        "canary": make_canary(streams.stream("canary")),
        "scenario_generator_version": GENERATOR_VERSION,
        "breaks": [_break_truth(plan, found["break_id"], rec)],
    }
    explanation: JSON = {
        "scenario_id": scenario_id,
        "generator_version": GENERATOR_VERSION,
        "seed": seed,
        "split": split,
        "currency": ccy,
        "as_of": as_of,
        "breaks": [
            {
                "break_id": found["break_id"],
                "break_type": plan.break_type,
                "variant": plan.variant,
                "explanation": plan.explanation,
                "events": [
                    {"event_id": e.event_id, "kind": e.kind, "at": e.at, "trade_id": e.trade_id, "note": e.note}
                    for t in sim.trades
                    for e in t.events
                ],
            }
        ],
    }
    return Scenario(scenario_id, bundle, truth, manifest, explanation)


def business_day(d: str) -> bool:
    return date.fromisoformat(d).weekday() < 5
