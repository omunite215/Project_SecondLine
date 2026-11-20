"""B8 settlement-instruction mismatch (§5, ADR-016: escalate to reference data, never edit SSI; ADR-017 B8 row:
no tool writes SSI, booking corrections citing an SSI cause are POLICY_DENIED; DG-1, DG-6; KG-04 K5).

The counterparty's standing instruction changed; the bank instructed against the old one, so the CSD rejects the
delivery. All SSIs, BICs and accounts are synthetic (BIC country `ZZ`, user-assigned): real entities' LEIs are
never paired with made-up settlement data (golden rule 2; KG-04 as-built note on K5). `SsiRecord` renders the
current SSI; it is also background in other worlds.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sl_factory.breaks import SETTLEMENT_STATUS, SSI_RECORD, BreakPlan
from sl_factory.lifecycle import Simulator, add_business_days, utc
from sl_factory.render import RecordIds, Records, evidence
from sl_factory.rng import IdMinter

VARIANTS = ("stale_ssi", "wrong_place")
TYPE = "B8_SSI_MISMATCH"


@dataclass
class SsiRecord:
    counterparty: str
    currency: str
    bic: str
    account: str
    place: str
    effective_date: str
    named: bool = False
    holdings: dict[str, int] = field(default_factory=dict)

    def render(self, ids: IdMinter, rec: RecordIds, as_of: str) -> Records:
        e = evidence(
            ids,
            "SSI_RECORD",
            "refdata_sim",
            utc(self.effective_date, 7),
            {
                "counterparty": self.counterparty,
                "currency": self.currency,
                "account": self.account,
                "bic": self.bic,
                "place_of_settlement": self.place,
                "effective_date": self.effective_date,
            },
            f"Standing settlement instruction for {self.counterparty} ({self.currency}) effective "
            f"{self.effective_date}: {self.bic} / {self.account} at {self.place}.",
        )
        if self.named:
            rec.named["ssi_record"] = e["record_id"]
        return Records(evidence=[e])


def _bic(sim: Simulator, name: str) -> str:
    return name[:4].upper() + "ZZ" + sim.rng.choice("23456789") + sim.rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ")


def ssi_for(sim: Simulator, counterparty: str, effective: str, named: bool = False) -> SsiRecord:
    return SsiRecord(
        counterparty,
        sim.currency,
        _bic(sim, counterparty),
        f"ZZ{sim.rng.randrange(10**9, 10**10)}",
        sim.rng.choice(("ZZCSDA", "ZZCSDB")),
        effective,
        named,
    )


def background(sim: Simulator) -> SsiRecord:
    c = sim.rng.choice(sim.world.counterparties).name
    return ssi_for(sim, c, add_business_days(sim.as_of, -sim.rng.randrange(20, 200)))


def build(sim: Simulator, variant: str) -> BreakPlan:
    t = sim.settled_trade(value_date=sim.as_of)
    t.events = [e for e in t.events if e.kind not in ("custodian_update", "settled")]
    current = ssi_for(sim, t.counterparty.name, add_business_days(t.trade_date, -sim.rng.randrange(1, 15)), True)
    sim.extras.append(current)
    if variant == "stale_ssi":
        used = _bic(sim, t.counterparty.name)
        while used == current.bic:
            used = _bic(sim, t.counterparty.name)
        detail = f"instructed BIC {used} does not match the standing instruction"
    elif variant == "wrong_place":
        used = "ZZCSDB" if current.place == "ZZCSDA" else "ZZCSDA"
        detail = f"instructed place of settlement {used} does not match the standing instruction"
    else:
        raise ValueError(f"unknown B8 variant {variant!r}")
    t.ext_status, t.settled_quantity = "FAILED", 0
    t.status_text = f"Settlement rejected: {detail}."
    cause = t.cause(sim.ids, "instruction_used_stale_ssi", utc(t.trade_date, 18, 5), detail)
    return BreakPlan(
        break_type=TYPE,
        variant=variant,
        trades=[t],
        root_cause="SSI_MISMATCH",
        allowed=[("ESCALATE", "SSI_MISMATCH")],
        forbidden=[
            ("BOOKING_CORRECTION", "SSI_MISMATCH"),
            ("ADJUSTMENT", "ROUNDING_DIFFERENCE"),
            ("CLASSIFY", "CUTOFF_TIMING"),
        ],
        required=(SETTLEMENT_STATUS,),
        named_required=(SSI_RECORD,),
        cause_event_ids=[cause],
        explanation=f"SSI mismatch: {t.trade_id} was instructed against an outdated standing instruction "
        f"({detail}). Escalate to reference data; editing the SSI or the booking is wrong.",
        severity="MEDIUM",
        queue="REFERENCE_DATA",
    )
