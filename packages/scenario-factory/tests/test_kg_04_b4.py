"""KG-04 K1 · ADR-016 B4 row · ADR-017 B4 row: FX revaluation with the designated (ECB) source."""

from decimal import Decimal
from typing import Any

import pytest
from sl_factory import fx
from sl_factory.generate import Scenario, generate_scenario


def _fx_break(s: Scenario) -> tuple[dict[str, Any], dict[str, Any]]:
    assert s.truth is not None
    (b,) = [b for b in s.bundle["breaks"] if not b.get("trade_ids") and "isin" not in b]
    (t,) = [t for t in s.truth["breaks"] if t["break_id"] == b["break_id"]]
    return b, t


def _reval(s: Scenario) -> Decimal:
    (e,) = [e for e in s.bundle["journal_entries"] if any(ln["account"] == "4200-USD" for ln in e["lines"])]
    return sum(
        (Decimal(ln["amount"]) * (1 if ln["side"] == "DR" else -1) for ln in e["lines"] if ln["account"] == "1500-USD"),
        Decimal(0),
    )


@pytest.mark.parametrize("variant", ["wrong_source", "stale", "holiday"])
@pytest.mark.parametrize("index", range(6))
def test_KG_04_b4_revalue_with_designated_rate(index: int, variant: str) -> None:
    s = generate_scenario("dev", index, break_type="B4_FX_REVALUATION", variant=variant)
    b, t = _fx_break(s)
    assert b["symptom"] == "CASH_DIFFERENCE" and b["currency"] == "USD"
    assert t["root_cause"] == "FX_RATE_SOURCE"
    assert {(o["type"], o["reason_code"]) for o in t["allowed_outcomes"]} == {("ADJUSTMENT", "FX_RATE_SOURCE")}
    d = Decimal(b["cash_difference"])
    assert {(c["account"], Decimal(c["delta"])) for c in t["expected_state_delta"]["cash"]} == {
        ("1500-USD", d),
        ("4200-USD", -d),
    }
    notices = {e["record_id"]: e for e in s.bundle["evidence"] if e["kind"] == "FX_RATE_NOTICE"}
    designated = [notices[i] for i in t["required_evidence_ids"] if i in notices]
    assert len(designated) == 1 and designated[0]["fields"]["rate_source"] == "ecb"
    as_of = s.bundle["as_of"]
    if variant == "holiday":
        assert as_of not in fx.ecb_eurusd()
        assert designated[0]["fields"]["as_of"] == fx.prior_ecb(as_of)
    else:
        assert designated[0]["fields"]["as_of"] == as_of
    if variant in ("wrong_source", "holiday"):
        assert any(n["fields"]["rate_source"] == "fed_h10" for n in notices.values())
    assert all(r["source"] == "ecb" for r in s.bundle["fx_rates"])  # contract: fx_rates are designated only
    assert _reval(s) != 0


def test_KG_04_background_fx_is_correct_and_common() -> None:
    with_fx = 0
    for i in range(60):
        s = generate_scenario("dev", i, break_type="B1_TIMING_CUTOFF")
        if s.bundle["fx_rates"]:
            with_fx += 1
            assert all(b.get("trade_ids") for b in s.bundle["breaks"])  # no FX break without a B4 cause
    assert 10 <= with_fx <= 40  # FX records appear in non-B4 worlds too (no family tell)
