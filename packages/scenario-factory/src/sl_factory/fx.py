"""FX facts from the KG-02 reference snapshots, read only through `sl_factory.refdata` (KG-04 K1/K11).

EUR/USD is the one pair both ECB (USD per EUR) and Fed H.10 (USD per EUR) publish directly, so B4 uses it.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from functools import cache

from sl_factory import refdata


def _ref(prefix: str) -> str:
    return max(r for r in refdata.refs() if r.startswith(prefix + "@"))


def _eurusd(prefix: str) -> dict[str, Decimal]:
    rows = refdata.snapshot(_ref(prefix), "rates.json")
    return {r["date"]: Decimal(r["rate"]) for r in rows if r["base"] == "EUR" and r["quote"] == "USD"}


@cache
def ecb_eurusd() -> dict[str, Decimal]:
    return _eurusd("ecb")


@cache
def h10_eurusd() -> dict[str, Decimal]:
    return _eurusd("h10")


@cache
def aligned_dates() -> tuple[str, ...]:
    """Dates both sources published (KG-02 aligned_with_ecb.json): the factory's as-of window (K11)."""
    return tuple(refdata.snapshot(_ref("h10"), "aligned_with_ecb.json"))


@cache
def ecb_holidays() -> tuple[str, ...]:
    """Weekdays inside the window with an H.10 rate but no ECB fixing (TARGET holidays)."""
    ecb, h10 = ecb_eurusd(), h10_eurusd()
    lo, hi = date.fromisoformat(min(ecb)), date.fromisoformat(max(h10))
    out, d = [], lo
    while d <= hi:
        s = d.isoformat()
        if d.weekday() < 5 and s not in ecb and s in h10:
            out.append(s)
        d += timedelta(days=1)
    return tuple(out)


def prior_ecb(d: str, n: int = 1) -> str:
    """The n-th ECB fixing date strictly before d."""
    return sorted(k for k in ecb_eurusd() if k < d)[-n]
