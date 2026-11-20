"""Synthetic world: institution, counterparties, instruments, markets (KG-03, §5, ADR-016, plan D3/D4).

ISINs use the ISO 6166 user-assigned prefix `QZ` with a valid check digit, so they can't collide with a real
security. Counterparties are generated names with no LEI/BIC until KG-02 reference data exists.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from decimal import Decimal

from sl_factory.rng import FORBIDDEN, IdMinter, Streams

CURRENCIES = ("USD", "EUR", "GBP", "CHF", "JPY")  # ADR-016 (a)
MINOR_UNITS = {"USD": 2, "EUR": 2, "GBP": 2, "CHF": 2, "JPY": 0}  # ISO 4217


@dataclass(frozen=True)
class Market:
    """Custodian market per currency: fixed standard-time UTC offset and a 16:00 local statement cutoff (synthetic)."""

    name: str
    utc_offset_hours: int
    cutoff_local_hour: int = 16

    @property
    def cutoff_utc_hour(self) -> int:
        return self.cutoff_local_hour - self.utc_offset_hours


MARKETS = {
    "USD": Market("America/New_York", -5),
    "EUR": Market("Europe/Frankfurt", 1),
    "GBP": Market("Europe/London", 0),
    "CHF": Market("Europe/Zurich", 1),
    "JPY": Market("Asia/Tokyo", 9),
}

# Price ranges per currency (synthetic, 4 dp booked prices).
PRICE_RANGE = {"USD": (5, 400), "EUR": (5, 300), "GBP": (2, 150), "CHF": (10, 500), "JPY": (300, 9000)}

_ADJ = (
    "Northwind",
    "Bluefield",
    "Harbor",
    "Silverline",
    "Granite",
    "Juniper",
    "Meridian",
    "Copperleaf",
    "Aldmoor",
    "Brightwater",
    "Kestrel",
    "Oakmont",
)
_NOUN = (
    "Widgets",
    "Logistics",
    "Foods",
    "Energy",
    "Materials",
    "Robotics",
    "Textiles",
    "Optics",
    "Shipping",
    "Utilities",
)
_SUFFIX = {"USD": "Corp", "EUR": "AG", "GBP": "plc", "CHF": "SA", "JPY": "KK"}
_BROKERS = ("Fernhill Securities", "Coldharbour Brokers", "Ashgrove Markets", "Larkspur Capital", "Tidewell Partners")


@dataclass(frozen=True)
class Instrument:
    isin: str
    currency: str
    name: str


@dataclass(frozen=True)
class Counterparty:
    cpty_id: str
    name: str


@dataclass(frozen=True)
class World:
    institution: str
    instruments: tuple[Instrument, ...]
    counterparties: tuple[Counterparty, ...]

    def instruments_in(self, currency: str) -> tuple[Instrument, ...]:
        return tuple(i for i in self.instruments if i.currency == currency)


def isin_check_digit(body: str) -> str:
    """ISO 6166 check digit over the first 11 characters (letters → 10..35, then Luhn)."""
    digits = "".join(str(int(c, 36)) for c in body)
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return str((10 - total % 10) % 10)


def _isin(rng: random.Random, used: set[str]) -> str:
    while True:
        body = "QZ" + "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(9))
        isin = body + isin_check_digit(body)
        if isin not in used and not FORBIDDEN.search(isin):
            used.add(isin)
            return isin


def build_world(streams: Streams, ids: IdMinter, per_currency: int = 3) -> World:
    rng = streams.stream("world")
    used: set[str] = set()
    instruments = []
    for ccy in CURRENCIES:
        for _ in range(per_currency):
            name = f"{rng.choice(_ADJ)} {rng.choice(_NOUN)} {_SUFFIX[ccy]} ord."
            instruments.append(Instrument(_isin(rng, used), ccy, name))
    brokers = rng.sample(_BROKERS, 3)
    counterparties = tuple(Counterparty(ids.mint("cpty"), b) for b in brokers)
    return World("Second-Line Synthetic Bank", tuple(instruments), counterparties)


def minor_unit(currency: str) -> Decimal:
    return Decimal(1).scaleb(-MINOR_UNITS[currency])
