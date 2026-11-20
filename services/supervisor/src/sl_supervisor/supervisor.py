"""The supervisor loop (KG-11; §8 detective monitors, ADR-004: halts FUTURE actions, never undoes commits).

process(envelope) → alerts. Dedupe by event_id; status per (invariant, subject); an alert only on a change to
violated; on an alert, halt the run once (monitor / full conditions only, ADR-014) and write an incident record.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from sl_supervisor.events import Event, ts
from sl_supervisor.invariants import Status, i9_suspense, i10_transitions, i11_freshness, i12_sequence
from sl_supervisor.ledger import LedgerReader
from sl_supervisor.state import RunState

HALTING_CONDITIONS = ("monitor", "full")


class HaltSink(Protocol):
    """Redis halt flag + OM-12 `POST /internal/v1/runs/{id}:halt` (not in the contracts yet; KG-11 S7)."""

    def halt(self, run_id: str, reason: str) -> None: ...


@dataclass
class RecordingHaltSink:
    halts: list[str] = field(default_factory=list)

    def halt(self, run_id: str, reason: str) -> None:
        self.halts.append(run_id)


@dataclass(frozen=True)
class Alert:
    invariant: str
    run_id: str
    subject: str
    detail: str
    event_id: str


def _utcnow() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class Supervisor:
    def __init__(
        self, ledger: LedgerReader, halt: HaltSink, condition: str = "monitor", now: Callable[[], str] = _utcnow
    ) -> None:
        self.ledger, self.halt_sink, self.condition, self.now = ledger, halt, condition, now
        self.runs: dict[str, RunState] = {}
        self.status: dict[tuple[str, str, str], bool] = {}
        self.incidents: list[dict[str, Any]] = []
        self.metrics: dict[str, float] = {"events": 0, "duplicates": 0, "alerts": 0, "max_consumer_lag_s": 0.0}

    def process(self, envelope: dict[str, Any]) -> list[Alert]:
        e = Event.from_envelope(envelope)
        st = self.runs.setdefault(e.run_id, RunState())
        if e.event_id in st.seen:
            self.metrics["duplicates"] += 1
            return []
        st.seen.add(e.event_id)
        self.metrics["events"] += 1
        now = self.now()
        lag = (ts(now) - ts(e.committed_at)).total_seconds()
        self.metrics["max_consumer_lag_s"] = max(self.metrics["max_consumer_lag_s"], lag)
        statuses: list[Status] = (
            i12_sequence.check(e, st)
            + i11_freshness.check(e, st)
            + i10_transitions.check(e, st)
            + i9_suspense.check(e, st, self.ledger)
        )
        alerts = []
        for s in statuses:
            key = (e.run_id, s.invariant, s.subject)
            was = self.status.get(key, False)
            self.status[key] = s.violated
            if s.violated and not was:
                alerts.append(Alert(s.invariant, e.run_id, s.subject, s.detail, e.event_id))
        for a in alerts:
            self.metrics["alerts"] += 1
            halted = self.condition in HALTING_CONDITIONS and not st.halted
            if halted:
                self.halt_sink.halt(a.run_id, f"{a.invariant}: {a.detail}")
                st.halted = True
            self.incidents.append(
                {
                    "run_id": a.run_id,
                    "invariant": a.invariant,
                    "subject": a.subject,
                    "detail": a.detail,
                    "event_id": a.event_id,
                    "detected_at": now,
                    "detection_delay_s": lag,
                    "halted": halted,
                    "condition": self.condition,
                }
            )
        return alerts
