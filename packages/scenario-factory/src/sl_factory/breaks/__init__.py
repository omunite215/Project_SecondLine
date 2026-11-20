"""Break generators B1–B3 (KG-03); B4–B8 arrive in KG-04.

A generator changes facts on `TradeSim`s through a cause event, and returns a `BreakPlan`: the oracle's view of
that cause (ADR-016 delta, ADR-017 evidence). It never writes a visible record; `render` does that from the facts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from sl_factory.lifecycle import TradeSim

Outcome = tuple[str, str]  # (ProposedAction.type, reason_code)

# Evidence the oracle requires, by role; resolved to record ids after render (ADR-017 "agent must cite").
SETTLEMENT_STATUS = "SETTLEMENT_STATUS"
BROKER_CONFIRM = "BROKER_CONFIRM"
CUSTODIAN_STATEMENT = "CUSTODIAN_STATEMENT"
BOOKING_TRADE_DATE = "INTERNAL_BOOKING:trade_date"
BOOKING_SETTLEMENT = "INTERNAL_BOOKING:settlement"


@dataclass(frozen=True)
class CashDelta:
    account: str
    currency: str
    delta: Decimal


@dataclass(frozen=True)
class SecDelta:
    account: str
    isin: str
    delta: int


@dataclass(frozen=True)
class PosDelta:
    isin: str
    basis: str
    delta: int


@dataclass
class BreakPlan:
    break_type: str
    variant: str
    trades: list[TradeSim]
    root_cause: str
    allowed: list[Outcome]
    forbidden: list[Outcome]
    required: tuple[str, ...]
    cause_event_ids: list[str]
    explanation: str
    severity: str
    maker_checker: bool = False
    queue: str = "OPERATIONS"
    cash: list[CashDelta] = field(default_factory=list)
    securities: list[SecDelta] = field(default_factory=list)
    positions: list[PosDelta] = field(default_factory=list)


def severity_for(amount: Decimal, currency: str) -> str:
    """Synthetic severity by absolute cash impact (JPY scaled ×100); proposal, reviewed with MET-11 in SH-06."""
    a = abs(amount) / (100 if currency == "JPY" else 1)
    if a < 1_000:
        return "LOW"
    if a < 100_000:
        return "MEDIUM"
    return "HIGH"
