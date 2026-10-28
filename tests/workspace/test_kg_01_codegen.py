"""KG-01 §19 · NFR-06: `make codegen-py` is deterministic and maps money to Decimal (golden rule 3)."""
import importlib.util
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures" / "schemas"


def _codegen(out: Path) -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "codegen_py.py"), "--schemas", str(FIXTURES),
                    "--out", str(out)], check=True, capture_output=True, text=True)


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
