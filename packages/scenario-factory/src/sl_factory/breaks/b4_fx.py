"""B4 FX rate / source (§5, ADR-016: revalue with the designated source, 1500 vs 4200, rate_id recorded;
ADR-017: cite a designated-source FX_RATE_NOTICE as of the valuation date + the INTERNAL_BOOKING; KG-04 K1).

The bank converted USD into EUR some days ago (1500 bridge, ADR-016 FX pattern) and revalues the EUR position in
USD today. The designated source is the ECB reference rate (on a TARGET holiday: the last prior fixing).
Variants: `wrong_source` (Fed H.10 used), `stale` (an earlier ECB fixing used), `holiday` (no ECB fixing today;
the bank used today's H.10 instead of the last ECB fixing). `FxRevaluation(correct=True)` is the same world with
the right rate — background in non-B4 scenarios, so FX records never mark the break family.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from sl_factory import fx
from sl_factory.breaks import BOOKING_FX, FX_NOTICE, BreakPlan, CashDelta, severity_for
from sl_factory.lifecycle import Simulator, add_business_days, dec_str, money, utc
from sl_factory.render import RecordIds, Records, evidence, line
from sl_factory.rng import IdMinter

VARIANTS = ("wrong_source", "stale", "holiday")
TYPE = "B4_FX_REVALUATION"


@dataclass
class FxRevaluation:
    exposure: int  # EUR held
    book_rate: Decimal  # USD per EUR at conversion (an earlier ECB fixing)
    conversion_date: str
    designated_as_of: str
    used_rate: Decimal
    used_source: str  # "ecb" | "fed_h10"
    used_as_of: str
    show_h10: bool  # the bank also receives the H.10 feed today (background noise either way)
    holdings: dict[str, int] = field(default_factory=dict)

    @property
    def designated_rate(self) -> Decimal:
        return fx.ecb_eurusd()[self.designated_as_of]

    def amount(self, rate: Decimal) -> Decimal:
        return money(self.exposure * (rate - self.book_rate), "USD")

    def render(self, ids: IdMinter, rec: RecordIds, as_of: str) -> Records:
        out = Records()
        cost = money(self.exposure * self.book_rate, "USD")
        out.journal.append(
            {
                "entry_id": ids.mint("jnl"),
                "booked_at": utc(self.conversion_date, 10),
                "lines": [
                    line("1500-USD", "DR", cost, "USD"),
                    line("1110-USD", "CR", cost, "USD"),
                    line("1110-EUR", "DR", Decimal(self.exposure), "EUR"),
                    line("1500-EUR", "CR", Decimal(self.exposure), "EUR"),
                ],
            }
        )
        reval = self.amount(self.used_rate)
        if reval:
            dr, cr = ("1500-USD", "4200-USD") if reval > 0 else ("4200-USD", "1500-USD")
            rec.named["fx_reval_entry"] = eid = ids.mint("jnl")
            out.journal.append(
                {
                    "entry_id": eid,
                    "booked_at": utc(as_of, 18),
                    "lines": [line(dr, "DR", abs(reval), "USD"), line(cr, "CR", abs(reval), "USD")],
                }
            )
        for d in sorted({fx.prior_ecb(as_of, n) for n in (1, 2, 3)} | ({as_of} & set(fx.ecb_eurusd()))):
            out.fx_rates.append(
                {
                    "rate_id": ids.mint("fxr"),
                    "base": "EUR",
                    "quote": "USD",
                    "rate": dec_str(fx.ecb_eurusd()[d]),
                    "source": "ecb",
                    "as_of": d,
                }
            )
        n = evidence(
            ids,
            "FX_RATE_NOTICE",
            "ecb_feed",
            utc(self.designated_as_of, 15, 10),
            {
                "base_currency": "EUR",
                "quote_currency": "USD",
                "rate": dec_str(self.designated_rate),
                "as_of": self.designated_as_of,
                "rate_source": "ecb",
            },
            f"ECB euro reference rate {self.designated_as_of}: 1 EUR = {dec_str(self.designated_rate)} USD.",
        )
        rec.named["fx_notice_designated"] = n["record_id"]
        out.evidence.append(n)
        if self.used_source == "ecb" and self.used_as_of != self.designated_as_of:
            out.evidence.append(
                evidence(
                    ids,
                    "FX_RATE_NOTICE",
                    "ecb_feed",
                    utc(self.used_as_of, 15, 10),
                    {
                        "base_currency": "EUR",
                        "quote_currency": "USD",
                        "rate": dec_str(self.used_rate),
                        "as_of": self.used_as_of,
                        "rate_source": "ecb",
                    },
                    f"ECB euro reference rate {self.used_as_of}: 1 EUR = {dec_str(self.used_rate)} USD.",
                )
            )
        if self.show_h10 or self.used_source == "fed_h10":
            h = fx.h10_eurusd().get(as_of)
            if h is not None:
                out.evidence.append(
                    evidence(
                        ids,
                        "FX_RATE_NOTICE",
                        "fed_h10_feed",
                        utc(as_of, 17, 30),
                        {
                            "base_currency": "EUR",
                            "quote_currency": "USD",
                            "rate": dec_str(h),
                            "as_of": as_of,
                            "rate_source": "fed_h10",
                        },
                        f"Fed H.10 noon buying rate {as_of}: 1 EUR = {dec_str(h)} USD.",
                    )
                )
        return out


def background(sim: Simulator) -> FxRevaluation:
    """A correctly revalued EUR position (no break)."""
    d = sim.as_of if sim.as_of in fx.ecb_eurusd() else fx.prior_ecb(sim.as_of)
    return _world(sim, designated_as_of=d, used_source="ecb", used_as_of=d)


def _world(sim: Simulator, *, designated_as_of: str, used_source: str, used_as_of: str) -> FxRevaluation:
    conv = fx.prior_ecb(sim.as_of, sim.rng.randrange(4, 9))
    used = fx.ecb_eurusd()[used_as_of] if used_source == "ecb" else fx.h10_eurusd()[used_as_of]
    return FxRevaluation(
        sim.rng.randrange(1_000, 50_000) * 100,
        fx.ecb_eurusd()[conv],
        conv,
        designated_as_of,
        used,
        used_source,
        used_as_of,
        show_h10=sim.rng.random() < 0.5,
    )


def build(sim: Simulator, variant: str) -> BreakPlan:
    today_ecb = sim.as_of in fx.ecb_eurusd()
    if variant == "wrong_source":
        x = _world(sim, designated_as_of=sim.as_of, used_source="fed_h10", used_as_of=sim.as_of)
        why = "the Fed H.10 noon rate"
    elif variant == "stale":
        x = _world(sim, designated_as_of=sim.as_of, used_source="ecb", used_as_of=fx.prior_ecb(sim.as_of, 1))
        why = f"the stale ECB fixing of {x.used_as_of}"
    elif variant == "holiday":
        if today_ecb:
            raise ValueError("B4 holiday needs an as-of without an ECB fixing")
        x = _world(sim, designated_as_of=fx.prior_ecb(sim.as_of), used_source="fed_h10", used_as_of=sim.as_of)
        why = "today's H.10 rate on a TARGET holiday instead of the last ECB fixing"
    else:
        raise ValueError(f"unknown B4 variant {variant!r}")
    if variant != "holiday" and not today_ecb:
        raise ValueError("B4 needs an as-of with an ECB fixing")
    d = x.amount(x.designated_rate) - x.amount(x.used_rate)
    if not d or not x.amount(x.used_rate):
        raise ValueError("B4: no revaluation difference on this date")  # caller redraws the date
    sim.extras.append(x)
    cause = sim.ids.mint("evt")
    sim.events.append(
        (
            cause,
            "fx_revaluation_rate_chosen",
            utc(sim.as_of, 18),
            f"revalued EUR {x.exposure} at {x.used_rate} ({x.used_source} {x.used_as_of})",
        )
    )
    return BreakPlan(
        break_type=TYPE,
        variant=variant,
        trades=[],
        root_cause="FX_RATE_SOURCE",
        allowed=[("ADJUSTMENT", "FX_RATE_SOURCE")],
        forbidden=[("ADJUSTMENT", "ROUNDING_DIFFERENCE"), ("CLASSIFY", "CUTOFF_TIMING")],
        required=(),
        named_required=(FX_NOTICE, BOOKING_FX),
        cause_event_ids=[cause],
        explanation=f"FX source: the EUR {x.exposure} position was revalued with {why}; the designated ECB rate "
        f"({x.designated_as_of}: {x.designated_rate}) gives a {d} USD difference. Adjust 1500 vs 4200.",
        severity=severity_for(d, "USD"),
        maker_checker=False,
        cash=[CashDelta("1500-USD", "USD", d), CashDelta("4200-USD", "USD", -d)],
        anchor_fx=True,
        category="stale_external_source" if variant == "stale" else "easy_structured",
    )


def holiday_as_of(pick_index: int) -> str:
    days = fx.ecb_holidays()
    return days[pick_index % len(days)]


def ecb_window_start() -> str:
    return add_business_days(min(fx.ecb_eurusd()), 10)
