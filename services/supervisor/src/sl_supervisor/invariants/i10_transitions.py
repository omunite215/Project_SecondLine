"""I10 valid cross-action transitions per break (§8, §15 family 1/3; KG-11 S4). Sticky: once a break has had an
invalid transition it stays violated (a later valid step doesn't undo a committed wrong one, ADR-004)."""

from __future__ import annotations

from sl_supervisor.events import CLASSIFIED, CLOSED, ESCALATED, MUTATIONS, Event
from sl_supervisor.invariants import Status
from sl_supervisor.state import RunState


def check(e: Event, st: RunState) -> list[Status]:
    b = st.brk(e.aggregate_id)
    why = ""
    if e.event_type in MUTATIONS and (b.escalated or b.closed):
        why = "mutation after the break was " + ("closed" if b.closed else "escalated")
    elif e.event_type == CLOSED and not (b.mutated or b.classified):
        why = "closed with no supporting mutation or classification"
    elif e.event_type == CLASSIFIED and b.mutated:
        why = "reclassified after a posting"
    b.mutated |= e.event_type in MUTATIONS
    b.classified |= e.event_type == CLASSIFIED
    b.escalated |= e.event_type == ESCALATED
    b.closed |= e.event_type == CLOSED
    if why:
        b.transition_violation = why
    return [Status("I10", e.aggregate_id, bool(b.transition_violation), b.transition_violation)]
