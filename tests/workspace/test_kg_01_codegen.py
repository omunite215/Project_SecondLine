"""KG-01 §19 · NFR-06: `make codegen-py` is deterministic and maps money to Decimal (golden rule 3)."""

import importlib.util
import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures" / "schemas"


def _codegen(out: Path) -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "codegen_py.py"), "--schemas", str(FIXTURES), "--out", str(out)],
        check=True,
        capture_output=True,
        text=True,
    )


def _tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*.py"))}


def _load(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("money_fixture", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # pydantic resolves postponed annotations via sys.modules
    spec.loader.exec_module(module)
    return module


def test_KG_01_codegen_deterministic(tmp_path: Path) -> None:
    _codegen(tmp_path / "a")
    _codegen(tmp_path / "b")
    a, b = _tree(tmp_path / "a"), _tree(tmp_path / "b")
    assert "actions/money_fixture.py" in a
    assert a == b
    assert not any(b"timestamp" in src for src in a.values())


def test_KG_01_codegen_money_is_decimal(tmp_path: Path) -> None:
    _codegen(tmp_path)
    model = _load(tmp_path / "actions" / "money_fixture.py").MoneyFixture
    doc = model.model_validate({"amount": "10.10", "currency": "USD"})
    assert type(doc.amount) is Decimal and doc.amount == Decimal("10.10")
    assert doc.model_dump(mode="json")["amount"] == "10.10"  # strings in JSON, never float


def test_KG_01_codegen_resolves_nested_relative_refs_offline(tmp_path: Path) -> None:
    # Regression: root → actions/parameters/leaf → ../../common (the truth → escalate → common chain in contracts).
    # Each schema has an https `$id`; refs must resolve as local files, never as remote URLs against the wrong base.
    base = "https://secondline.invalid/contracts/1/"
    docs: dict[str, dict[str, object]] = {
        "common.schema.json": {"$defs": {"uuid": {"type": "string", "format": "uuid"}}},
        "actions/parameters/leaf.schema.json": {
            "type": "object",
            "properties": {"queue_id": {"$ref": "../../common.schema.json#/$defs/uuid"}},
        },
        "scenario/root.schema.json": {
            "type": "object",
            "properties": {"queue_id": {"$ref": "../actions/parameters/leaf.schema.json#/properties/queue_id"}},
        },
    }
    schemas = tmp_path / "schemas"
    for rel, doc in docs.items():
        p = schemas / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": base + rel, **doc}))
    script = str(ROOT / "scripts" / "codegen_py.py")
    r = subprocess.run(
        [sys.executable, script, "--schemas", str(schemas), "--out", str(tmp_path / "o")],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert (tmp_path / "o" / "scenario" / "root.py").is_file()


def test_KG_01_committed_models_are_current(tmp_path: Path) -> None:
    # Same check CI runs as `make codegen-py && git diff --exit-code`: committed models == fresh codegen.
    committed = ROOT / "packages" / "contracts" / "py" / "src" / "sl_contracts" / "_generated"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "codegen_py.py"), "--out", str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert committed.is_dir(), "run `make codegen-py`"
    assert _tree(committed) == _tree(tmp_path), "stale sl_contracts models: run `make codegen-py`"
