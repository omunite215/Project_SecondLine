"""KG-04 K3–K5 · ADR-016 B6/B7/B8 rows · ADR-017: corporate action, settlement shortfall, SSI mismatch."""

from typing import Any

import pytest
from sl_factory.generate import Scenario, generate_scenario

EMPTY = {"cash": [], "securities": [], "positions": []}


def _one(s: Scenario) -> tuple[dict[str, Any], dict[str, Any]]:
    assert s.truth is not None
    (t,) = s.truth["breaks"]
    (b,) = [b for b in s.bundle["breaks"] if b["break_id"] == t["break_id"]]
    return b, t


def _out(xs: list[dict[str, str]]) -> set[tuple[str, str]]:
    return {(o["type"], o["reason_code"]) for o in xs}


def _ev(s: Scenario, ids: list[str], kind: str) -> list[dict[str, Any]]:
    return [e for e in s.bundle["evidence"] if e["record_id"] in ids and e["kind"] == kind]


@pytest.mark.parametrize("variant", ["wrong_ex_date", "wrong_entitlement"])
@pytest.mark.parametrize("index", range(6))
def test_KG_04_b6_split_per_notice(index: int, variant: str) -> None:
    s = generate_scenario("dev", index, break_type="B6_CORPORATE_ACTION", variant=variant)
    b, t = _one(s)
    (notice,) = _ev(s, t["required_evidence_ids"], "CA_NOTICE")
    (cust,) = _ev(s, t["required_evidence_ids"], "CUSTODIAN_STATEMENT")
    n, d = int(notice["fields"]["ratio_new"]), int(notice["fields"]["ratio_old"])
    isin = b["isin"]
    s100 = sum(
        int(m["quantity"]) * (1 if m["side"] == "DR" else -1)
        for m in s.bundle["securities_movements"]
        if m["account"] == f"S100-{isin}"
    )
    dq = int(b["quantity_difference"])
    assert b["symptom"] == "POSITION_DIFFERENCE" and b["trade_ids"] == []
    assert int(cust["fields"]["quantity"]) - s100 == dq != 0
    assert int(cust["fields"]["quantity"]) * d % n == 0  # whole-share entitlement
    assert _out(t["allowed_outcomes"]) == {("CORPORATE_ACTION", "CORPORATE_ACTION_SPLIT")}
    assert t["approval_requirements"] == {"maker_checker": True}  # ADR-014: CA always needs approval
    assert {(x["account"], int(x["delta"])) for x in t["expected_state_delta"]["securities"]} == {
        (f"S100-{isin}", dq),
        (f"S900-{isin}", -dq),
    }


@pytest.mark.parametrize("variant", ["cash", "securities"])
@pytest.mark.parametrize("index", range(6))
def test_KG_04_b7_shortfall_escalates_never_plugs(index: int, variant: str) -> None:
    s = generate_scenario("dev", index, break_type="B7_SETTLEMENT_SHORTFALL", variant=variant)
    b, t = _one(s)
    assert b["symptom"] == "SETTLEMENT_FAILURE"
    assert _out(t["allowed_outcomes"]) == {("ESCALATE", "CASH_SHORTFALL")}
    assert ("ADJUSTMENT", "ROUNDING_DIFFERENCE") in _out(t["forbidden_outcomes"])  # the 4100 plug
    assert ("CLASSIFY", "CUTOFF_TIMING") in _out(t["forbidden_outcomes"])  # DG-1
    assert t["expected_state_delta"] == EMPTY
    assert t["escalation_if_insufficient_evidence"]["queue"] == ("TREASURY" if variant == "cash" else "OPERATIONS")
    (status,) = _ev(s, t["required_evidence_ids"], "SETTLEMENT_STATUS")
    assert status["fields"]["status"] == "FAILED"
    if "status_code" in status["fields"]:
        assert status["fields"]["status_code"] in {"MONY", "CMON", "LACK", "CLAC"}


@pytest.mark.parametrize("variant", ["stale_ssi", "wrong_place"])
@pytest.mark.parametrize("index", range(6))
def test_KG_04_b8_ssi_mismatch_escalates_to_reference_data(index: int, variant: str) -> None:
    s = generate_scenario("dev", index, break_type="B8_SSI_MISMATCH", variant=variant)
    b, t = _one(s)
    assert b["symptom"] == "SETTLEMENT_FAILURE"  # same symptom as B7: the evidence must tell them apart
    assert _out(t["allowed_outcomes"]) == {("ESCALATE", "SSI_MISMATCH")}
    assert ("BOOKING_CORRECTION", "SSI_MISMATCH") in _out(t["forbidden_outcomes"])
    assert t["escalation_if_insufficient_evidence"]["queue"] == "REFERENCE_DATA"
    (ssi,) = _ev(s, t["required_evidence_ids"], "SSI_RECORD")
    assert ssi["fields"]["bic"][4:6] == "ZZ"  # synthetic BIC (user-assigned country)
    assert t["expected_state_delta"] == EMPTY


def test_KG_04_ca_and_ssi_records_also_appear_without_their_break() -> None:
    kinds_without = {"CA_NOTICE": 0, "SSI_RECORD": 0}
    for i in range(80):
        s = generate_scenario("dev", i, break_type="B1_TIMING_CUTOFF")
        present = {e["kind"] for e in s.bundle["evidence"]}
        for k in kinds_without:
            kinds_without[k] += k in present
    assert all(10 <= v <= 50 for v in kinds_without.values()), kinds_without
