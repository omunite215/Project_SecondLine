"""KG-04 K2 · ADR-016 B5 row · ADR-017 B5 row, DG-2, DG-5: missing vs duplicate vs separate executions."""

from typing import Any

import pytest

from sl_factory.generate import Scenario, generate_scenario


def _one(s: Scenario) -> tuple[dict[str, Any], dict[str, Any]]:
    assert s.truth is not None
    (t,) = s.truth["breaks"]
    (b,) = [b for b in s.bundle["breaks"] if b["break_id"] == t["break_id"]]
    return b, t


def _out(xs: list[dict[str, str]]) -> set[tuple[str, str]]:
    return {(o["type"], o["reason_code"]) for o in xs}


@pytest.mark.parametrize("index", range(6))
def test_KG_04_b5_missing_trade(index: int) -> None:
    s = generate_scenario("dev", index, break_type="B5_MISSING_OR_DUPLICATE_TRADE", variant="missing")
    b, t = _one(s)
    assert b["symptom"] == "UNMATCHED_TRADE" and b["trade_ids"] == [] and int(b["quantity_difference"]) > 0
    refs = {e["fields"].get("trade_ref") for e in s.bundle["evidence"] if e["kind"] == "BROKER_CONFIRM"}
    assert refs - {tr["trade_id"] for tr in s.bundle["trades"]}  # a confirm the bank can't match
    assert _out(t["allowed_outcomes"]) == {("ESCALATE", "MISSING_TRADE")}


@pytest.mark.parametrize("index", range(6))
def test_KG_04_b5_duplicate_reversed_in_full(index: int) -> None:
    s = generate_scenario("dev", index, break_type="B5_MISSING_OR_DUPLICATE_TRADE", variant="duplicate")
    b, t = _one(s)
    (dup,) = b["trade_ids"]
    q = int(next(tr for tr in s.bundle["trades"] if tr["trade_id"] == dup)["quantity"])
    assert b["symptom"] == "UNMATCHED_TRADE" and int(b["quantity_difference"]) == -q
    assert _out(t["allowed_outcomes"]) == {("BOOKING_CORRECTION", "DUPLICATE_TRADE")}
    assert t["approval_requirements"] == {"maker_checker": True}
    assert sorted(int(x["delta"]) for x in t["expected_state_delta"]["securities"]) == [-q, q]
    assert all(int(p["delta"]) == -q for p in t["expected_state_delta"]["positions"])
    assert s.explanation is not None and s.explanation["breaks"][0]["balanced_but_false"] is True


@pytest.mark.parametrize("index", range(6))
def test_KG_04_b5_separate_executions_are_not_duplicates(index: int) -> None:
    s = generate_scenario("dev", index, break_type="B5_MISSING_OR_DUPLICATE_TRADE", variant="separate_executions")
    b, t = _one(s)
    (late,) = b["trade_ids"]
    twin = [
        tr
        for tr in s.bundle["trades"]
        if tr["trade_id"] != late
        and (tr["isin"], tr["quantity"], tr["price"])
        == next((x["isin"], x["quantity"], x["price"]) for x in s.bundle["trades"] if x["trade_id"] == late)
    ]
    assert twin, "the trap needs an identical-looking twin booking"
    confirmed = {e["fields"]["trade_ref"] for e in s.bundle["evidence"] if e["kind"] == "BROKER_CONFIRM"}
    assert {late, twin[0]["trade_id"]} <= confirmed  # both executions are confirmed
    assert _out(t["allowed_outcomes"]) == {("CLASSIFY", "CUTOFF_TIMING")}
    assert ("BOOKING_CORRECTION", "DUPLICATE_TRADE") in _out(t["forbidden_outcomes"])
    assert t["expected_state_delta"] == {"cash": [], "securities": [], "positions": []}


@pytest.mark.parametrize("index", range(6))
def test_KG_04_b5_delayed_confirm_is_escalated(index: int) -> None:
    s = generate_scenario("dev", index, break_type="B5_MISSING_OR_DUPLICATE_TRADE", variant="delayed_confirm")
    b, t = _one(s)
    assert b["symptom"] == "UNMATCHED_TRADE" and "quantity_difference" not in b
    assert _out(t["allowed_outcomes"]) == {("ESCALATE", "INSUFFICIENT_EVIDENCE")}
    assert s.explanation is not None and s.explanation["breaks"][0]["category"] == "missing_evidence"
