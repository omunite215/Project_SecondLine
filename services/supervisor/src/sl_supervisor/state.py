"""Per-run supervisor state (KG-11)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BreakState:
    mutated: bool = False
    classified: bool = False
    escalated: bool = False
    closed: bool = False
    transition_violation: str = ""
    last_committed: str | None = None
    last_version: int | None = None
    versions: dict[int, str] = field(default_factory=dict)


@dataclass
class RunState:
    seen: set[str] = field(default_factory=set)
    breaks: dict[str, BreakState] = field(default_factory=dict)
    suspense_flags: set[str] = field(default_factory=set)
    halted: bool = False

    def brk(self, aggregate_id: str) -> BreakState:
        return self.breaks.setdefault(aggregate_id, BreakState())
