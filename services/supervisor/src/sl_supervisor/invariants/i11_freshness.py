"""I11 temporal freshness and as-of consistency (§8; KG-11 S5). MAX_COMMIT_LAG_S is a placeholder, tuned on dev
only and frozen before KG-18."""

from __future__ import annotations

from sl_supervisor.events import Event, ts
from sl_supervisor.invariants import Status
from sl_supervisor.state import RunState

MAX_COMMIT_LAG_S = 60.0


def check(e: Event, st: RunState) -> list[Status]:
    b = st.brk(e.aggregate_id)
    lag = (ts(e.committed_at) - ts(e.occurred_at)).total_seconds()
    why = ""
    if lag > MAX_COMMIT_LAG_S:
        why = f"committed {lag:.0f}s after it occurred (> {MAX_COMMIT_LAG_S:.0f}s)"
    elif b.last_committed and ts(e.committed_at) < ts(b.last_committed):
        why = "committed_at went backwards within the break"
    b.last_committed = max(b.last_committed or e.committed_at, e.committed_at, key=ts)
    return [Status("I11", e.aggregate_id, bool(why), why)]
