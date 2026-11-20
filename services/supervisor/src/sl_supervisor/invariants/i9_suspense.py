"""I9 suspicious suspense growth (§8; ADR-016: an agent may never post to 1900; KG-11 S3: threshold 0, policy)."""

from __future__ import annotations

from sl_supervisor.events import MUTATIONS, Event
from sl_supervisor.invariants import Status
from sl_supervisor.ledger import LedgerReader
from sl_supervisor.state import RunState


def check(e: Event, st: RunState, ledger: LedgerReader) -> list[Status]:
    if e.event_type not in MUTATIONS or not e.transaction_id:
        return []
    lines = ledger.transaction_lines(e.run_id, e.transaction_id)
    if lines is None:  # fail closed: a mutation the authority can't show is itself an alarm (golden rule 7)
        st.suspense_flags.add(e.transaction_id)
        return [Status("I9", e.run_id, True, f"transaction {e.transaction_id} unverifiable at the ledger")]
    if e.by_agent and any(ln.account.startswith("1900-") for ln in lines):
        st.suspense_flags.add(e.transaction_id)
    return [
        Status(
            "I9",
            e.run_id,
            bool(st.suspense_flags),
            f"agent posting to suspense in {sorted(st.suspense_flags)}" if st.suspense_flags else "",
        )
    ]
