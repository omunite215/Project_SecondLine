"""KG-01 §21 · NFR-11: the uv workspace exposes every Python member as an importable package."""

import importlib
import re
import tomllib
from pathlib import Path

import pytest

MEMBERS = ["sl_contracts", "sl_factory", "sl_eval", "sl_audit", "sl_agent", "sl_supervisor", "sl_mcp"]


@pytest.mark.parametrize("module", MEMBERS)
def test_KG_01_every_member_imports(module: str) -> None:
    assert importlib.import_module(module).__name__ == module


ROOT = Path(__file__).resolve().parents[2]
UNPRIVILEGED = ["services/agent", "services/supervisor", "services/mcp-adapter"]
PRIVILEGED = {"sl-factory", "sl-eval"}


def _deps(member: str) -> set[str]:
    project = tomllib.loads((ROOT / member / "pyproject.toml").read_text())["project"]
    names = list(project.get("dependencies", []))
    for group in project.get("optional-dependencies", {}).values():
        names += group
    return {re.split(r"[\s\[<>=!~;]", n, maxsplit=1)[0].lower().replace("_", "-") for n in names}


@pytest.mark.parametrize("member", UNPRIVILEGED)
def test_KG_01_unprivileged_members_dont_depend_on_privileged(member: str) -> None:
    # Golden rule 4: hidden truth lives only in the factory and evaluation packages.
    assert not _deps(member) & PRIVILEGED, f"{member} must not depend on {PRIVILEGED}"


def test_KG_01_contracts_declare_their_runtime_deps() -> None:
    # Generated models are pydantic v2 classes: a non-dev install (service images) must pull pydantic in.
    assert "pydantic" in _deps("packages/contracts/py")


@pytest.mark.parametrize("member", ["services/agent", "services/supervisor"])
def test_KG_01_services_depend_on_contracts(member: str) -> None:
    # Cross-service shapes come only from sl_contracts (golden rule 8).
    assert "sl-contracts" in _deps(member)
