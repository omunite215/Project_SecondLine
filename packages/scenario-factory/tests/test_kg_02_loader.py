"""KG-02 done criterion (§6, SEC-14): the factory reads reference data only via MANIFEST, hash-verified."""

import ast
import shutil
from pathlib import Path

import pytest
from sl_factory import refdata
from sl_factory.refdata import RefdataError, snapshot

SRC = Path(refdata.__file__).resolve().parent


def test_KG_02_factory_reads_refdata_only_via_manifest() -> None:
    assert {r.split("@")[0] for r in refdata.refs()} == {"ecb", "h10", "gleif", "iso20022"}
    ecb_ref = next(r for r in refdata.refs() if r.startswith("ecb@"))
    rates = snapshot(ecb_ref, "rates.json")
    assert rates and {"date", "base", "quote", "rate"} == set(rates[0]) and isinstance(rates[0]["rate"], str)
    # no other sl_factory module names the reference directory: refdata.py is the single entry point
    for p in sorted(SRC.rglob("*.py")):
        if p.name == "refdata.py":
            continue
        strings = [
            n.value
            for n in ast.walk(ast.parse(p.read_text()))
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
        ]
        assert not any(s == "reference" or "data/reference" in s for s in strings), f"{p.name} reads data/reference"


def test_KG_02_loader_rejects_tampered_or_unlisted(tmp_path: Path) -> None:
    root = tmp_path / "reference"
    shutil.copytree(refdata.REF_ROOT, root)
    ref = next(r for r in refdata.refs(root) if r.startswith("iso20022@"))
    assert snapshot(ref, "settlement_codes.json", root)
    with pytest.raises(RefdataError, match="not listed"):
        snapshot(ref, "other.json", root)
    with pytest.raises(RefdataError, match="not in MANIFEST"):
        snapshot("ecb@1999-01-01", "rates.json", root)
    p = root / "iso20022" / ref.split("@")[1] / "settlement_codes.json"
    p.write_text(p.read_text().replace("LACK", "LACX"))
    with pytest.raises(RefdataError, match="sha256 mismatch"):
        snapshot(ref, "settlement_codes.json", root)
