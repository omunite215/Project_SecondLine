"""KG-03 done criteria (T-DOM-02, ADR-015, golden rule 4): same seed ⇒ identical hash; no truth leaks into the bundle;
`make factory SPLIT=dev N=40` writes data/generated/dev/ (plan steps 8–10)."""

import json
import re
import subprocess
from pathlib import Path

from factory_testlib import ROOT, assert_valid, no_float
from hypothesis import given, settings
from hypothesis import strategies as st
from sl_factory.canonical import dumps, sha256_ref
from sl_factory.generate import VARIANTS, generate_scenario

BREAK_VARIANTS = [(b, v) for b, vs in VARIANTS.items() for v in vs]
REASON_CODES = json.loads((ROOT / "packages/contracts/common.schema.json").read_text())["$defs"]["reason_code"]["enum"]
BREAK_TYPES = json.loads((ROOT / "packages/contracts/common.schema.json").read_text())["$defs"]["break_type"]["enum"]
PRIVILEGED_NAMES = [
    "root_cause",
    "break_type",
    "causal_event",
    "allowed_outcomes",
    "forbidden_outcomes",
    "expected_state_delta",
    "truth",
    "canary",
    "SLCANARY",
    "explanation",
    "severity",
]


def test_KG_03_same_seed_identical_hash() -> None:
    for b, v in BREAK_VARIANTS:
        a, b2 = (
            generate_scenario("dev", 3, break_type=b, variant=v),
            generate_scenario("dev", 3, break_type=b, variant=v),
        )
        assert dumps(a.bundle) == dumps(b2.bundle) and dumps(a.truth) == dumps(b2.truth)
        assert a.manifest == b2.manifest
        assert a.manifest["snapshot_hash"] == sha256_ref(a.bundle)
    assert (
        generate_scenario("dev", 3).manifest["snapshot_hash"] != generate_scenario("dev", 4).manifest["snapshot_hash"]
    )


@settings(max_examples=200, deadline=None)
@given(index=st.integers(min_value=0, max_value=100_000), which=st.sampled_from(BREAK_VARIANTS))
def test_KG_03_property_no_truth_leak(index: int, which: tuple[str, str]) -> None:
    s = generate_scenario("dev", index, break_type=which[0], variant=which[1])
    visible = (dumps(s.bundle) + dumps(s.manifest)).decode()
    assert s.truth is not None
    needles = [s.truth["canary"], *REASON_CODES, *BREAK_TYPES, *PRIVILEGED_NAMES]
    for br in s.truth["breaks"]:
        needles += br["causal_event_ids"]
    for needle in needles:
        assert needle not in visible, f"{needle!r} leaked into the agent-visible bundle/manifest"
    assert not re.search(r"\bevt_", visible)  # causal events never render


@settings(max_examples=100, deadline=None)
@given(index=st.integers(min_value=0, max_value=100_000), which=st.sampled_from(BREAK_VARIANTS))
def test_KG_03_no_side_channel_tells(index: int, which: tuple[str, str]) -> None:
    # Leakage review: field presence and price precision must not mark the break family.
    s = generate_scenario("dev", index, break_type=which[0], variant=which[1])
    for e in s.bundle["evidence"]:
        if e["kind"] == "BROKER_CONFIRM":
            assert len(e["fields"]["price"].split(".")[1]) == 8, e  # every confirm has 8 dp
        if e["kind"] == "SETTLEMENT_STATUS":
            assert "cutoff_time" in e["fields"], e  # every status names its cutoff


def test_KG_03_make_factory_dev_writes_40(tmp_path: Path) -> None:
    r = subprocess.run(
        ["make", "-s", "factory", "SPLIT=dev", "N=40", f"OUT={tmp_path}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    split = tmp_path / "dev"
    bundles = sorted((split / "bundles").glob("*.json"))
    assert len(bundles) == 40
    for sub in ("truth", "manifests"):
        assert sorted(p.name for p in (split / sub).glob("scn_*.json")) == [p.name for p in bundles]
    for p in bundles:
        bundle = json.loads(p.read_text())
        no_float(bundle)
        assert_valid("scenario/world_bundle.schema.json", bundle)
        assert_valid("scenario/truth.schema.json", json.loads((split / "truth" / p.name).read_text()))
        manifest = json.loads((split / "manifests" / p.name).read_text())
        assert_valid("scenario/manifest.schema.json", manifest)
        assert manifest["snapshot_hash"] == sha256_ref(bundle)
    index = json.loads((split / "MANIFEST.json").read_text())
    assert index["count"] == 40 and len(index["scenarios"]) == 40
    assert "truth" not in json.dumps(index)  # truth hashes live in truth/INDEX.json only
    assert len(json.loads((split / "truth" / "INDEX.json").read_text())["scenarios"]) == 40
    types = [json.loads((split / "truth" / p.name).read_text())["breaks"][0]["break_type"] for p in bundles]
    assert set(types) == set(VARIANTS)  # all three generators represented
