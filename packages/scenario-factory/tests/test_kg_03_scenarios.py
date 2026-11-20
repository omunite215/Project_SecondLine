"""KG-03 §5 · ADR-016 · ADR-017 · T-DOM-02: clean lifecycle, contract validity and the B1–B3 generators
(plan steps 3–7)."""

from collections import defaultdict
from decimal import Decimal
from typing import Any

import pytest
from factory_testlib import assert_valid, no_float
from hypothesis import given, settings
from hypothesis import strategies as st
from sl_factory.generate import VARIANTS, Scenario, generate_scenario
from sl_factory.world import MINOR_UNITS

BREAK_VARIANTS = [(b, v) for b, vs in VARIANTS.items() for v in vs]


def _evidence(s: Scenario, kind: str) -> list[dict[str, Any]]:
    return [e for e in s.bundle["evidence"] if e["kind"] == kind]


def _trade(s: Scenario, trade_id: str) -> dict[str, Any]:
    return next(t for t in s.bundle["trades"] if t["trade_id"] == trade_id)


def _by_ref(records: list[dict[str, Any]], trade_id: str) -> dict[str, Any]:
    return next(e for e in records if e["fields"].get("trade_ref") == trade_id)


def _only_break(s: Scenario) -> tuple[dict[str, Any], dict[str, Any]]:
    assert s.truth is not None
    assert len(s.bundle["breaks"]) == 1 and len(s.truth["breaks"]) == 1
    return s.bundle["breaks"][0], s.truth["breaks"][0]


def _delta_sums(delta: dict[str, Any]) -> tuple[dict[str, Decimal], dict[str, int]]:
    cash: dict[str, Decimal] = defaultdict(Decimal)
    sec: dict[str, int] = defaultdict(int)
    for line in delta["cash"]:
        cash[line["currency"]] += Decimal(line["delta"])
    for line in delta["securities"]:
        sec[line["isin"]] += int(line["delta"])
    return cash, sec


def _outcomes(xs: list[dict[str, str]]) -> set[tuple[str, str]]:
    return {(o["type"], o["reason_code"]) for o in xs}


# ---- step 3: clean world -------------------------------------------------------------------------------------
@pytest.mark.parametrize("index", range(20))
def test_KG_03_clean_lifecycle_balances_and_has_no_breaks(index: int) -> None:
    s = generate_scenario("dev", index, break_type=None)
    assert s.truth is None and s.bundle["breaks"] == []
    for entry in s.bundle["journal_entries"]:
        per_ccy: dict[str, Decimal] = defaultdict(Decimal)
        for line in entry["lines"]:
            amt = Decimal(line["amount"])
            assert -amt.as_tuple().exponent <= MINOR_UNITS[line["currency"]], line  # type: ignore[operator]
            per_ccy[line["currency"]] += amt if line["side"] == "DR" else -amt
        assert all(v == 0 for v in per_ccy.values()), entry  # I1 per currency
    per_trade_isin: dict[tuple[str, str], int] = defaultdict(int)
    for m in s.bundle["securities_movements"]:
        q = int(m["quantity"])
        per_trade_isin[(m["trade_id"], m["isin"])] += q if m["side"] == "DR" else -q
    assert all(v == 0 for v in per_trade_isin.values())
    # no schema check here: a bundle must carry ≥1 break by contract, so a clean world is internal only


# ---- step 4: every generator emits contract-valid documents --------------------------------------------------
@settings(max_examples=150, deadline=None)
@given(index=st.integers(min_value=0, max_value=10_000), which=st.sampled_from(BREAK_VARIANTS))
def test_KG_03_outputs_validate_against_contracts(index: int, which: tuple[str, str]) -> None:
    s = generate_scenario("dev", index, break_type=which[0], variant=which[1])
    assert_valid("scenario/world_bundle.schema.json", s.bundle)
    assert_valid("scenario/truth.schema.json", s.truth)
    assert_valid("scenario/manifest.schema.json", s.manifest)
    for doc in (s.bundle, s.truth, s.manifest, s.explanation):
        no_float(doc)
    bundle_ids = {t["trade_id"] for t in s.bundle["trades"]} | {e["entry_id"] for e in s.bundle["journal_entries"]}
    bundle_ids |= {e["record_id"] for e in s.bundle["evidence"]} | {
        m["movement_id"] for m in s.bundle["securities_movements"]
    }
    _, truth = _only_break(s)
    assert set(truth["required_evidence_ids"]) <= bundle_ids
    cash, sec = _delta_sums(truth["expected_state_delta"])
    assert all(v == 0 for v in cash.values()) and all(v == 0 for v in sec.values())  # deltas balance too


# ---- step 5: B1 timing / cutoff ------------------------------------------------------------------------------
@pytest.mark.parametrize("variant", VARIANTS["B1_TIMING_CUTOFF"])
@pytest.mark.parametrize("index", range(8))
def test_KG_03_b1_timing(index: int, variant: str) -> None:
    s = generate_scenario("dev", index, break_type="B1_TIMING_CUTOFF", variant=variant)
    symptom, truth = _only_break(s)
    assert truth["root_cause"] == "CUTOFF_TIMING"
    assert _outcomes(truth["allowed_outcomes"]) == {("CLASSIFY", "CUTOFF_TIMING")}
    assert {o[0] for o in _outcomes(truth["forbidden_outcomes"])} >= {"BOOKING_CORRECTION", "ADJUSTMENT"}
    assert truth["expected_state_delta"] == {"cash": [], "securities": [], "positions": []}
    (tid,) = symptom["trade_ids"]
    status = _by_ref(_evidence(s, "SETTLEMENT_STATUS"), tid)
    assert status["fields"]["status"] == "MATCHED"
    assert status["fields"]["settle_date"] > status["fields"]["value_date"] == _trade(s, tid)["settlement_date"]
    assert status["record_id"] in truth["required_evidence_ids"]
    assert symptom["symptom"] == "POSITION_DIFFERENCE"
    assert int(symptom["quantity_difference"]) == -int(_trade(s, tid)["quantity"])  # statement lacks the receipt


# ---- step 6: B2 quantity -------------------------------------------------------------------------------------
@pytest.mark.parametrize("index", range(10))
def test_KG_03_b2_booking_error_rebooks_at_evidenced_quantity(index: int) -> None:
    s = generate_scenario("dev", index, break_type="B2_QUANTITY_MISMATCH", variant="booking_error")
    symptom, truth = _only_break(s)
    (tid,) = symptom["trade_ids"]
    trade, confirm = _trade(s, tid), _by_ref(_evidence(s, "BROKER_CONFIRM"), tid)
    booked, evidenced = int(trade["quantity"]), int(confirm["fields"]["quantity"])
    assert booked != evidenced
    assert truth["root_cause"] == "QUANTITY_MISMATCH" and truth["approval_requirements"] == {"maker_checker": True}
    assert _outcomes(truth["allowed_outcomes"]) == {("BOOKING_CORRECTION", "QUANTITY_MISMATCH")}
    delta = truth["expected_state_delta"]
    isin = trade["isin"]
    assert {(d["account"], int(d["delta"])) for d in delta["securities"]} == {
        (f"S100-{isin}", evidenced - booked),
        (f"S900-{isin}", booked - evidenced),
    }
    assert {(p["basis"], int(p["delta"])) for p in delta["positions"]} == {
        ("TRADING", evidenced - booked),
        ("SETTLED", evidenced - booked),
    }
    ccy = trade["currency"]
    d = Decimal(confirm["fields"]["gross"]) - Decimal(_booked_gross(s, tid))
    assert {(c["account"], Decimal(c["delta"])) for c in delta["cash"]} == {(f"1300-{ccy}", d), (f"1110-{ccy}", -d)}
    assert confirm["record_id"] in truth["required_evidence_ids"]


def _booked_gross(s: Scenario, tid: str) -> str:
    entry = next(
        e for e in s.bundle["journal_entries"] if e["trade_id"] == tid and e["lines"][0]["account"].startswith("1300")
    )
    return str(entry["lines"][0]["amount"])


@pytest.mark.parametrize("index", range(8))
def test_KG_03_b2_partial_settlement_lookalike_is_not_a_booking_error(index: int) -> None:
    s = generate_scenario("dev", index, break_type="B2_QUANTITY_MISMATCH", variant="partial_settlement")
    symptom, truth = _only_break(s)
    (tid,) = symptom["trade_ids"]
    trade, confirm = _trade(s, tid), _by_ref(_evidence(s, "BROKER_CONFIRM"), tid)
    status = _by_ref(_evidence(s, "SETTLEMENT_STATUS"), tid)
    assert trade["quantity"] == confirm["fields"]["quantity"]  # the booking is right
    assert status["fields"]["status"] == "PARTIALLY_SETTLED"
    assert 0 < int(status["fields"]["quantity"]) < int(trade["quantity"])
    assert symptom["symptom"] == "POSITION_DIFFERENCE"
    assert truth["break_type"] == "B2_QUANTITY_MISMATCH" and truth["root_cause"] == "PARTIAL_SETTLEMENT"
    assert _outcomes(truth["allowed_outcomes"]) == {
        ("CLASSIFY", "PARTIAL_SETTLEMENT"),
        ("ESCALATE", "PARTIAL_SETTLEMENT"),
    }
    assert ("BOOKING_CORRECTION", "QUANTITY_MISMATCH") in _outcomes(truth["forbidden_outcomes"])
    assert truth["expected_state_delta"] == {"cash": [], "securities": [], "positions": []}


# ---- step 7: B3 price / rounding at the tolerance boundary ---------------------------------------------------
def _b3(
    index: int, variant: str, currency: str | None = None
) -> tuple[Scenario, dict[str, Any], dict[str, Any], Decimal]:
    s = generate_scenario("dev", index, break_type="B3_PRICE_ROUNDING", variant=variant, currency=currency)
    symptom, truth = _only_break(s)
    unit = Decimal(1).scaleb(-MINOR_UNITS[symptom["currency"]])
    return s, symptom, truth, unit * len(symptom["trade_ids"])


@pytest.mark.parametrize("currency", ["USD", "EUR", "JPY"])
@pytest.mark.parametrize("variant", ["within_tolerance", "at_tolerance"])
@pytest.mark.parametrize("index", range(5))
def test_KG_03_b3_rounding_within_tolerance_is_adjustable(index: int, variant: str, currency: str) -> None:
    s, symptom, truth, tolerance = _b3(index, variant, currency)
    diff = Decimal(symptom["cash_difference"])
    assert symptom["symptom"] == "CASH_DIFFERENCE" and symptom["currency"] == currency
    assert 0 < abs(diff) <= tolerance
    if variant == "at_tolerance":
        assert abs(diff) == tolerance
    assert truth["root_cause"] == "ROUNDING_DIFFERENCE"
    assert _outcomes(truth["allowed_outcomes"]) == {("ADJUSTMENT", "ROUNDING_DIFFERENCE")}
    assert {(c["account"], Decimal(c["delta"])) for c in truth["expected_state_delta"]["cash"]} == {
        (f"4100-{currency}", diff),
        (f"1210-{currency}", -diff),
    }
    for tid in symptom["trade_ids"]:  # cause visible in evidence: booked price = confirm price rounded to 4 dp
        confirm_price = Decimal(_by_ref(_evidence(s, "BROKER_CONFIRM"), tid)["fields"]["price"])
        assert Decimal(_trade(s, tid)["price"]) == confirm_price.quantize(Decimal("0.0001"), rounding="ROUND_HALF_EVEN")
    if variant == "within_tolerance":
        assert len(symptom["trade_ids"]) == 3 and abs(diff) < tolerance


@pytest.mark.parametrize("currency", ["USD", "JPY"])
@pytest.mark.parametrize("index", range(5))
def test_KG_03_b3_one_unit_above_tolerance_escalates(index: int, currency: str) -> None:
    _, symptom, truth, tolerance = _b3(index, "above_tolerance", currency)
    unit = Decimal(1).scaleb(-MINOR_UNITS[currency])
    assert abs(Decimal(symptom["cash_difference"])) == tolerance + unit
    assert truth["root_cause"] == "PRICE_MISMATCH"
    assert _outcomes(truth["allowed_outcomes"]) == {("ESCALATE", "PRICE_MISMATCH")}
    assert ("ADJUSTMENT", "ROUNDING_DIFFERENCE") in _outcomes(truth["forbidden_outcomes"])  # DG-3 plug
    assert truth["expected_state_delta"] == {"cash": [], "securities": [], "positions": []}
