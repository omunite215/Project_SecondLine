"""I12 audit-sequence integrity per aggregate (§8, §12 ordering per key; KG-11 S6): version = previous + 1."""

from __future__ import annotations

from sl_supervisor.events import Event
from sl_supervisor.invariants import Status
from sl_supervisor.state import RunState


def check(e: Event, st: RunState) -> list[Status]:
    b = st.brk(e.aggregate_id)
    v = e.aggregate_version
    why = ""
    if v in b.versions and b.versions[v] != e.event_id:
        why = f"fork: version {v} committed twice"
    elif b.last_version is not None and v != b.last_version + 1:
        why = f"gap: version {v} after {b.last_version}"
    elif b.last_version is None and v != 1:
        why = f"gap: first version seen is {v}"
    b.versions.setdefault(v, e.event_id)
    b.last_version = max(v, b.last_version or 0)
    return [Status("I12", e.aggregate_id, bool(why), why)]
