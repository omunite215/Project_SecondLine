"""One scenario: seed → world → lifecycle → cause → visible records → recon → truth + manifest (KG-03).

Order matters and is fixed: ids, world, picks, lifecycle. Same (split, index, args) ⇒ same bytes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sl_factory import fx
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
    b4_fx,
    b5_trade,
    b6_corporate_action,
    b7_shortfall,
    b8_ssi,
)
from sl_factory.canonical import sha256_ref
from sl_factory.lifecycle import Simulator, dec_str
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
    b4_fx.TYPE: b4_fx.VARIANTS,
    b5_trade.TYPE: b5_trade.VARIANTS,
    b6_corporate_action.TYPE: b6_corporate_action.VARIANTS,
    b7_shortfall.TYPE: b7_shortfall.VARIANTS,
    b8_ssi.TYPE: b8_ssi.VARIANTS,
}
_BUILDERS: dict[str, Callable[[Simulator, str], BreakPlan]] = {
    b1_timing.TYPE: b1_timing.build,
    b2_quantity.TYPE: b2_quantity.build,
    b3_price_rounding.TYPE: b3_price_rounding.build,
    b4_fx.TYPE: b4_fx.build,
    b5_trade.TYPE: b5_trade.build,
    b6_corporate_action.TYPE: b6_corporate_action.build,
    b7_shortfall.TYPE: b7_shortfall.build,
    b8_ssi.TYPE: b8_ssi.build,
}
# Shares of worlds that also carry a correctly processed FX revaluation / corporate action / SSI record, so those
# record kinds never mark their break family (leakage review, KG-03/KG-04).
_BACKGROUND = {b4_fx.TYPE: 0.4, b6_corporate_action.TYPE: 0.25, b8_ssi.TYPE: 0.3}
_ATTEMPTS = 25


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    bundle: JSON  # agent-visible
    truth: JSON | None  # privileged; None for a clean (no-break) world
    manifest: JSON  # agent-visible
    explanation: JSON | None  # privileged sidecar (plan D1)


def _required_ids(plan: BreakPlan, rec: RecordIds) -> list[str]:
    out: set[str] = {rec.named[k] for k in plan.named_required}
    for t in plan.trades:
        for role in plan.required:
            if role == SETTLEMENT_STATUS:
                out.add(rec.status[t.trade_id])
            elif role == BROKER_CONFIRM:
                out.add(rec.confirm[t.trade_id])
            elif role == CUSTODIAN_STATEMENT:
                out.add(rec.custodian[t.isin])
            elif role == BOOKING_TRADE_DATE and t.trade_id in rec.trade_entry:
                out.add(rec.trade_entry[t.trade_id])
            elif role == BOOKING_SETTLEMENT and t.trade_id in rec.settle_entry:
                out.add(rec.settle_entry[t.trade_id])
            elif role in (BOOKING_TRADE_DATE, BOOKING_SETTLEMENT):
                continue  # that booking doesn't exist in this world (e.g. B5 missing trade)
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


def _as_of(break_types: list[str], variants: list[str], pick: Any) -> str:
    if "holiday" in [v for b, v in zip(break_types, variants, strict=True) if b == b4_fx.TYPE]:
        return b4_fx.holiday_as_of(pick.randrange(1000))
    window = [d for d in fx.aligned_dates() if d >= b4_fx.ecb_window_start()]
    return str(pick.choice(window))


def _match(plans: list[BreakPlan], found: list[JSON], scenario_id: str) -> list[tuple[BreakPlan, JSON]]:
    """Each recon break belongs to exactly one plan (a cause the recon can't find, or a break with no cause,
    is a generator bug)."""
    pairs = []
    left = list(found)
    for p in plans:

        def hit(b: JSON, p: BreakPlan = p) -> bool:
            if p.anchor_fx:
                return "isin" not in b and not b.get("trade_ids")
            if p.anchor_isin:
                return b.get("isin") == p.anchor_isin
            return set(b.get("trade_ids", [])) == {t.trade_id for t in p.trades}

        m = [b for b in left if hit(b)]
        if len(m) != 1:
            raise RuntimeError(f"{scenario_id}: plan {p.break_type}/{p.variant} matched {len(m)} recon breaks")
        pairs.append((p, m[0]))
        left.remove(m[0])
    if left:
        raise RuntimeError(f"{scenario_id}: {len(left)} recon break(s) with no cause")
    return pairs


def generate_scenario(
    split: str, index: int, break_type: str | None = AUTO, variant: str | None = None, currency: str | None = None
) -> Scenario:
    """One scenario. A generator that finds its drawn date infeasible (e.g. no FX difference) raises ValueError
    and the scenario is redrawn from the next attempt's sub-seed: still deterministic per (split, index, args)."""
    last: Exception | None = None
    for attempt in range(_ATTEMPTS):
        try:
            return _generate(split, index, attempt, break_type, variant, currency)
        except ValueError as e:
            last = e
    raise RuntimeError(f"{split}/{index}: no feasible draw in {_ATTEMPTS} attempts: {last}")


def _generate(
    split: str, index: int, attempt: int, break_type: str | None, variant: str | None, currency: str | None
) -> Scenario:
    seed = derive_seed(split, index) if attempt == 0 else derive_seed(f"{split}~{attempt}", index)
    streams = Streams(seed)
    ids = IdMinter(streams.stream("ids"))
    scenario_id = ids.mint("scn")
    world = build_world(streams, ids)
    pick = streams.stream("pick")
    if break_type == AUTO:
        break_type = tuple(VARIANTS)[index % len(VARIANTS)]
    if break_type is not None and variant is None:
        variant = pick.choice(VARIANTS[break_type])
    types = [break_type] if break_type else []
    variants = [variant or ""] if break_type else []
    ccy = currency or pick.choice(CURRENCIES)
    as_of = _as_of(types, variants, pick)
    sim = Simulator(streams.stream("lifecycle"), ids, world, ccy, as_of)
    for _ in range(pick.randrange(1, 5)):
        sim.settled_trade()  # background trades that reconcile cleanly
    plans = [_BUILDERS[b](sim, v) for b, v in zip(types, variants, strict=True)]
    for _ in range(pick.randrange(0, 4)):
        sim.pending_trade()
    if b4_fx.TYPE not in types and pick.random() < _BACKGROUND[b4_fx.TYPE]:
        sim.extras.append(b4_fx.background(sim))
    if b6_corporate_action.TYPE not in types and pick.random() < _BACKGROUND[b6_corporate_action.TYPE]:
        sim.extras.append(b6_corporate_action.background(sim))
    if pick.random() < _BACKGROUND[b8_ssi.TYPE]:
        sim.extras.append(b8_ssi.background(sim))

    bundle, rec = render(sim.trades, ids, scenario_id, as_of, sim.extras)
    bundle["breaks"] = reconcile(bundle, ids)
    manifest: JSON = {
        "scenario_id": scenario_id,
        "schema_version": "1.0",
        "snapshot_hash": sha256_ref(bundle),
        "source_snapshot_refs": [SOURCE_REF],
        "initial_state_ref": f"snapshot/{scenario_id}",
    }
    if not plans:
        if bundle["breaks"]:
            raise RuntimeError(f"clean world {scenario_id} produced breaks")  # pragma: no cover
        return Scenario(scenario_id, bundle, None, manifest, None)
    pairs = _match(plans, bundle["breaks"], scenario_id)
    truth: JSON = {
        "truth_version": "1.0",
        "scenario_id": scenario_id,
        "canary": make_canary(streams.stream("canary")),
        "scenario_generator_version": GENERATOR_VERSION,
        "breaks": [_break_truth(p, b["break_id"], rec) for p, b in pairs],
    }
    events = [
        {"event_id": e.event_id, "kind": e.kind, "at": e.at, "trade_id": e.trade_id, "note": e.note}
        for t in sim.trades
        for e in t.events
    ]
    events += [{"event_id": eid, "kind": kind, "at": at, "note": note} for eid, kind, at, note in sim.events]
    explanation: JSON = {
        "scenario_id": scenario_id,
        "generator_version": GENERATOR_VERSION,
        "seed": seed,
        "split": split,
        "currency": ccy,
        "as_of": as_of,
        "breaks": [
            {
                "break_id": b["break_id"],
                "break_type": p.break_type,
                "variant": p.variant,
                "category": p.category,
                "balanced_but_false": p.balanced_but_false,
                "explanation": p.explanation,
            }
            for p, b in pairs
        ],
        "events": events,
    }
    return Scenario(scenario_id, bundle, truth, manifest, explanation)
