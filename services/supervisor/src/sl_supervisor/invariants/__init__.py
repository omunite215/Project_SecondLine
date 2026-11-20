"""Detective invariants I9–I12 (§8). Each returns the *current* status of the subjects an event touches; the
alerter turns status changes into alerts, so a persisting violation alerts once (KG-11)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Status:
    invariant: str
    subject: str  # what the status is about: a run, or a break (aggregate)
    violated: bool
    detail: str = ""
