"""Ledger event envelope (packages/contracts/events/envelope.schema.json) as the supervisor reads it (KG-11)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# KG-11 S2: the event types the monitors key on. Om's OM-13 outbox must emit these names (or rename here).
MUTATIONS = frozenset({"ledger.adjustment_posted", "ledger.booking_corrected", "ledger.corporate_action_applied"})
CLASSIFIED, ESCALATED, CLOSED = "ledger.break_classified", "ledger.break_escalated", "ledger.break_closed"
EVENT_TYPES = MUTATIONS | {CLASSIFIED, ESCALATED, CLOSED}
_REQUIRED = (
    "event_id",
    "run_id",
    "actor_id",
    "event_type",
    "occurred_at",
    "committed_at",
    "aggregate_id",
    "aggregate_version",
)


def ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


@dataclass(frozen=True)
class Event:
    event_id: str
    run_id: str
    actor_id: str
    event_type: str
    occurred_at: str
    committed_at: str
    aggregate_id: str
    aggregate_version: int
    transaction_id: str | None

    @classmethod
    def from_envelope(cls, e: dict[str, Any]) -> Event:
        missing = [k for k in _REQUIRED if k not in e]
        if missing:
            raise ValueError(f"envelope missing {missing}")
        return cls(
            e["event_id"],
            e["run_id"],
            e["actor_id"],
            e["event_type"],
            e["occurred_at"],
            e["committed_at"],
            e["aggregate_id"],
            int(e["aggregate_version"]),
            e.get("transaction_id"),
        )

    @property
    def by_agent(self) -> bool:
        return self.actor_id.startswith("agt_")


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    """Sample-event source (KG-11 S8); the Kafka adapter arrives with OM-13."""
    with path.open() as f:
        for line in f:
            if line.strip():
                yield json.loads(line)
