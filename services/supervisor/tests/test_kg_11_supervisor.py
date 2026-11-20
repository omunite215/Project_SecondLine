"""KG-11 (§8 §12, REQ-008 REQ-010, T-SEC-03 T-SWE-03, I9–I12, MET-10, ADR-004): detective monitors alert once per
state change, halt future actions in monitor/full conditions, never alarm on legitimate sequences."""

from __future__ import annotations

import itertools
import uuid
from decimal import Decimal
from typing import Any

import pytest
from sl_supervisor.ledger import FakeLedger, Line
from sl_supervisor.supervisor import RecordingHaltSink, Supervisor

RUN = str(uuid.UUID(int=1))
_ids = itertools.count(1)


def ev(
    event_type: str,
    version: int,
    *,
    aggregate: str = "brk_Ab12Cd34Ef",
    actor: str = "agt_run0000001",
    occurred: str = "2026-03-02T17:00:00Z",
    committed: str = "2026-03-02T17:00:01Z",
    tx: str | None = None,
    event_id: str | None = None,
) -> dict[str, Any]:
    e = {
        "event_id": event_id or str(uuid.UUID(int=10_000 + next(_ids))),
        "run_id": RUN,
        "scenario_id": "scn_Zx81Kq0p",
        "actor_id": actor,
        "event_type": event_type,
        "schema_version": "1.0",
        "occurred_at": occurred,
        "committed_at": committed,
        "aggregate_id": aggregate,
        "aggregate_version": version,
        "correlation_id": str(uuid.UUID(int=7)),
        "payload_hash": "sha256:" + "ab" * 32,
        "evidence_hashes": [],
        "redaction_class": "INTERNAL",
    }
    if tx:
        e["transaction_id"] = tx
    return e


def sup(condition: str = "monitor", ledger: FakeLedger | None = None) -> tuple[Supervisor, RecordingHaltSink]:
    sink = RecordingHaltSink()
    return Supervisor(ledger or FakeLedger(), sink, condition=condition, now=lambda: "2026-03-02T17:00:05Z"), sink


def rounding_tx(ledger: FakeLedger, account: str = "4100-USD") -> str:
    tx = str(uuid.uuid4())
    ledger.add(RUN, tx, [Line("1300-USD", "DR", Decimal("0.01"), "USD"), Line(account, "CR", Decimal("0.01"), "USD")])
    return tx


# ---- legitimate sequences: zero alarms ---------------------------------------------------------------------
def test_KG_11_legitimate_sequences_raise_no_alarms() -> None:
    ledger = FakeLedger()
    s, sink = sup(ledger=ledger)
    flows = [
        [ev("ledger.break_classified", 1, aggregate="brk_A0000001")],
        [
            ev("ledger.adjustment_posted", 1, aggregate="brk_B0000001", tx=rounding_tx(ledger)),
            ev("ledger.break_closed", 2, aggregate="brk_B0000001"),
        ],
        [ev("ledger.break_escalated", 1, aggregate="brk_C0000001")],
        [
            ev("ledger.booking_corrected", 1, aggregate="brk_D0000001", tx=rounding_tx(ledger, "1110-USD")),
            ev("ledger.break_closed", 2, aggregate="brk_D0000001"),
        ],
    ]
    alerts = [a for flow in flows for e in flow for a in s.process(e)]
    assert alerts == [] and sink.halts == []
    dup = flows[0][0]
    assert s.process(dup) == [] and s.metrics["duplicates"] == 1  # replay is deduped, not an alarm


# ---- scripted violations: detected, exactly once ---------------------------------------------------------
def _scripted(ledger: FakeLedger) -> dict[str, list[dict[str, Any]]]:
    return {
        "I9": [ev("ledger.adjustment_posted", 1, aggregate="brk_E0000001", tx=rounding_tx(ledger, "1900-USD"))],
        "I10": [
            ev("ledger.break_escalated", 1, aggregate="brk_F0000001"),
            ev("ledger.adjustment_posted", 2, aggregate="brk_F0000001", tx=rounding_tx(ledger)),
        ],
        "I11": [ev("ledger.break_classified", 1, aggregate="brk_G0000001", occurred="2026-03-02T16:00:00Z")],
        "I12": [
            ev("ledger.break_classified", 1, aggregate="brk_H0000001"),
            ev("ledger.break_escalated", 3, aggregate="brk_H0000001"),
        ],
    }


@pytest.mark.parametrize("invariant", ["I9", "I10", "I11", "I12"])
def test_KG_11_scripted_violations_detected_once(invariant: str) -> None:
    ledger = FakeLedger()
    s, sink = sup(ledger=ledger)
    seq = _scripted(ledger)[invariant]
    alerts = [a for e in seq for a in s.process(e)]
    assert [a.invariant for a in alerts] == [invariant]
    # the violating state persists over later events on the same subject: still one alert (PoC repeat defect)
    later = ev(
        "ledger.break_closed",
        seq[-1]["aggregate_version"] + 1,
        aggregate=seq[-1]["aggregate_id"],
        occurred=seq[-1]["occurred_at"],
    )
    assert [a for a in s.process(later) if a.invariant == invariant] == []
    assert sink.halts == [RUN]  # halts future actions once per run
    (inc,) = [i for i in s.incidents if i["invariant"] == invariant]
    assert inc["run_id"] == RUN and inc["detection_delay_s"] >= 0


def test_KG_11_alert_rearms_after_recovery() -> None:
    s, _ = sup()
    a1 = s.process(ev("ledger.break_classified", 1, aggregate="brk_J0000001", occurred="2026-03-02T16:00:00Z"))
    ok = s.process(ev("ledger.break_escalated", 2, aggregate="brk_J0000001"))
    a2 = s.process(ev("ledger.break_closed", 3, aggregate="brk_J0000001", occurred="2026-03-02T16:00:00Z"))
    assert [a.invariant for a in a1 + ok + a2] == ["I11", "I11"]  # OK in between re-arms the alert


def test_KG_11_i12_fork_is_a_violation() -> None:
    s, _ = sup()
    s.process(ev("ledger.break_classified", 1, aggregate="brk_K0000001"))
    alerts = s.process(ev("ledger.break_escalated", 1, aggregate="brk_K0000001"))  # same version, new event_id
    assert [a.invariant for a in alerts] == ["I12"]


def test_KG_11_controls_off_never_halts() -> None:
    ledger = FakeLedger()
    s, sink = sup(condition="off", ledger=ledger)
    alerts = s.process(ev("ledger.adjustment_posted", 1, tx=rounding_tx(ledger, "1900-USD")))
    assert [a.invariant for a in alerts] == ["I9"] and sink.halts == []  # off: log, never block (ADR-014)


def test_KG_11_unknown_transaction_is_reported_not_guessed() -> None:
    s, _ = sup()
    alerts = s.process(ev("ledger.adjustment_posted", 1, tx=str(uuid.uuid4())))
    assert [a.invariant for a in alerts] == ["I9"] and "unverifiable" in alerts[0].detail  # fail closed (rule 7)


def test_KG_11_metrics_consumer_lag_and_detection_delay() -> None:
    s, _ = sup()
    s.process(ev("ledger.break_classified", 1, aggregate="brk_L0000001", occurred="2026-03-02T16:00:00Z"))
    assert s.metrics["events"] == 1 and s.metrics["max_consumer_lag_s"] == 4.0  # now − committed_at
    assert s.incidents[0]["detection_delay_s"] == 4.0
