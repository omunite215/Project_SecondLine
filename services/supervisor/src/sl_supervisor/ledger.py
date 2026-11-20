"""Ledger read port (KG-11 S1). The event envelope carries no payload, so the supervisor reads a transaction's
lines from the ledger, the financial authority, by `transaction_id`.

The contract has no such endpoint yet (neither main nor contracts 2.0.0, #37); Om adds it to the ledger internal
API, and an HTTP implementation of `LedgerReader` follows. `FakeLedger` serves tests and sample-event runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class Line:
    account: str
    side: str  # DR | CR
    amount: Decimal
    currency: str


class LedgerReader(Protocol):
    def transaction_lines(self, run_id: str, transaction_id: str) -> list[Line] | None:
        """The committed lines, or None if the ledger doesn't know the transaction."""
        ...


class FakeLedger:
    def __init__(self) -> None:
        self._tx: dict[tuple[str, str], list[Line]] = {}

    def add(self, run_id: str, transaction_id: str, lines: list[Line]) -> None:
        self._tx[(run_id, transaction_id)] = lines

    def transaction_lines(self, run_id: str, transaction_id: str) -> list[Line] | None:
        return self._tx.get((run_id, transaction_id))
