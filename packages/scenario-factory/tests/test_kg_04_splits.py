"""KG-04 done criteria (§14, §5, ADR-014/015, K6–K12): `make factory-all` reproducible; stratification + balance;
split universes disjoint; eval/blind outputs only under data/generated/{eval,blind}/. Eval/blind content is only
ever compared as bytes or counted; no assertion message prints it (K12)."""

import json
import subprocess
from collections import Counter
from pathlib import Path

import pytest
from factory_testlib import ROOT, assert_valid
from sl_factory import splits
from sl_factory.canonical import dumps
from sl_factory.generate import generate_scenario


def test_KG_04_eval_balance() -> None:
    slots = splits.plan("eval")
    assert len(slots) == 200
    cells = Counter((s.pressure, s.injection) for s in slots)
    assert set(cells.values()) == {25} and len(cells) == 8  # 4 pressure × 2 injection × 25 (§14)
    assert set(Counter(s.break_type for s in slots).values()) == {25}  # explicit break-type balance
    for cell in cells:
        per_type = Counter(s.break_type for s in slots if (s.pressure, s.injection) == cell)
        assert set(per_type.values()) <= {3, 4} and len(per_type) == 8
    assert "## eval: 200 scenario(s)" in splits.balance_tables("eval", slots)


def test_KG_04_dev_blind_matched_plans() -> None:
    dev, blind, matched = splits.plan("dev"), splits.plan("blind"), splits.matched_plan()
    assert len(dev) == 40 and set(Counter(s.break_type for s in dev).values()) == {5}
    assert len(blind) == 40 and {s.category for s in blind} == {"out_of_distribution"}
    assert len(matched) == 160 and {s.injection for s in matched} == {"none"}
    by_base = Counter(s.index for s in matched)
    assert len(by_base) == 40 and set(by_base.values()) == {4}
    for s in dev:  # every planned category is applicable to its variant
        assert s.category in splits.cats.applicable(s.break_type, s.variant)


def test_KG_04_split_universes_and_templates_disjoint() -> None:
    u = splits.UNIVERSES
    for a, b in (("dev", "eval"), ("dev", "blind"), ("eval", "blind")):
        assert not set(u[a].adjectives) & set(u[b].adjectives)
        assert not set(u[a].brokers) & set(u[b].brokers)
        assert u[a].phrasing != u[b].phrasing
        assert u[a].band[1] < u[b].band[0] or u[b].band[1] < u[a].band[0]
        ta = {s.template_id(a) for s in splits.plan(a)}
        tb = {s.template_id(b) for s in splits.plan(b)}
        assert not ta & tb


def test_KG_04_treatment_labels_never_reach_the_bundle() -> None:
    a = generate_scenario("dev", 7, break_type="B2_QUANTITY_MISMATCH", variant="booking_error", pressure="L0")
    b = generate_scenario("dev", 7, break_type="B2_QUANTITY_MISMATCH", variant="booking_error", pressure="L3")
    assert dumps(a.bundle) == dumps(b.bundle)  # pressure lives only in the privileged run_manifest
    assert (
        a.run_manifest
        and b.run_manifest
        and (a.run_manifest["pressure_level"], b.run_manifest["pressure_level"]) == ("L0", "L3")
    )
    c = generate_scenario("dev", 7, break_type="B2_QUANTITY_MISMATCH", variant="booking_error", injection="present")
    kinds = Counter(e["kind"] for e in c.bundle["evidence"]) - Counter(e["kind"] for e in a.bundle["evidence"])
    assert kinds == Counter({"COUNTERPARTY_MESSAGE": 1})
    for s in (a, b, c):
        assert_valid("scenario/run_manifest.schema.json", s.run_manifest)


@pytest.mark.parametrize("bt,variant", [("B1_TIMING_CUTOFF", "cutoff"), ("B2_QUANTITY_MISMATCH", "booking_error")])
def test_KG_04_missing_evidence_means_escalate(bt: str, variant: str) -> None:
    s = generate_scenario("dev", 3, break_type=bt, variant=variant, category="missing_evidence")
    assert s.truth is not None
    (t,) = s.truth["breaks"]
    assert [(o["type"], o["reason_code"]) for o in t["allowed_outcomes"]] == [("ESCALATE", "INSUFFICIENT_EVIDENCE")]
    assert t["expected_state_delta"] == {"cash": [], "securities": [], "positions": []}


def test_KG_04_multi_step_world_has_two_causes() -> None:
    s = generate_scenario(
        "dev", 5, break_type="B2_QUANTITY_MISMATCH", variant="booking_error", category="multi_step_dependencies"
    )
    assert s.truth is not None and len(s.truth["breaks"]) == 2 == len(s.bundle["breaks"])
    assert_valid("scenario/truth.schema.json", s.truth)


def _files(base: Path) -> dict[str, bytes]:
    return {p.relative_to(base).as_posix(): p.read_bytes() for p in sorted(base.rglob("*.json"))}


def test_KG_04_factory_all_reproducible(tmp_path: Path) -> None:
    runs = []
    for name in ("a", "b"):
        r = subprocess.run(
            ["make", "-s", "factory-all", f"OUT={tmp_path / name}"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=900,
        )
        assert r.returncode == 0, r.stderr[-2000:]
        assert "## eval: 200 scenario(s)" in r.stdout and "## blind: 40 scenario(s)" in r.stdout
        runs.append(tmp_path / name)
    assert sorted(p.name for p in runs[0].iterdir()) == ["blind", "dev", "eval"]  # nothing outside the splits
    fa, fb = _files(runs[0]), _files(runs[1])
    assert fa.keys() == fb.keys() and all(fa[k] == fb[k] for k in fa), "factory-all is not byte-reproducible"
    counts = {s: json.loads((runs[0] / s / "MANIFEST.json").read_text())["count"] for s in ("dev", "eval", "blind")}
    assert counts == {"dev": 40, "eval": 200, "blind": 40}
    matched = json.loads((runs[0] / "eval" / "truth" / "matched" / "MATCHED.json").read_text())
    assert len(matched["pairs"]) == 160
    bbf = sum(
        b["balanced_but_false"]
        for p in (runs[0] / "eval" / "truth" / "explanations").glob("*.json")
        for b in json.loads(p.read_text())["breaks"]
    )
    assert bbf > 0  # ≥1 balanced-but-false case (§5)


def test_KG_04_no_message_or_status_tells() -> None:
    # Leakage review: counterparty mail headers come from one shared pool whatever the category or treatment;
    # no status record carries status_code; no interim marker text reaches the agent.
    from sl_factory.categories import SUBJECTS

    for i, (cat, inj) in enumerate(
        [
            (None, "none"),
            ("manipulated_memo", "none"),
            ("contradictory_evidence", "none"),
            ("unstructured_ambiguous", "none"),
            (None, "present"),
        ]
        * 6
    ):
        s = generate_scenario("dev", i, break_type="B1_TIMING_CUTOFF", variant="cutoff", category=cat, injection=inj)
        text = dumps(s.bundle).decode()
        assert "PLACEHOLDER" not in text and "status_code" not in text
        for e in s.bundle["evidence"]:
            if e["kind"] == "COUNTERPARTY_MESSAGE":
                assert e["fields"]["subject"] in SUBJECTS
