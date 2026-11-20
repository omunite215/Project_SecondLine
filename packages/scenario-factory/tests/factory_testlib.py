"""Shared helpers for KG-03 factory tests: contract-schema validation (packages/contracts is the only source
of shapes)."""

import json
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[3]
CONTRACTS = ROOT / "packages" / "contracts"
ID_BASE = "https://secondline.invalid/contracts/1/"


@cache
def _registry() -> Registry:
    resources = []
    for p in sorted(CONTRACTS.rglob("*.schema.json")):
        if "py" in p.relative_to(CONTRACTS).parts:
            continue
        doc = json.loads(p.read_text())
        resources.append((doc["$id"], Resource.from_contents(doc)))
    return Registry().with_resources(resources)


@cache
def validator(rel: str) -> Draft202012Validator:
    schema = _registry().contents(ID_BASE + rel)
    return Draft202012Validator(schema, registry=_registry())


def assert_valid(rel: str, doc: Any) -> None:
    errors = sorted(validator(rel).iter_errors(doc), key=lambda e: list(e.absolute_path))
    assert not errors, f"{rel}: " + "; ".join(f"{list(e.absolute_path)}: {e.message[:160]}" for e in errors[:5])


def no_float(obj: Any) -> None:
    """Round-trip through JSON with floats forbidden (golden rule 3: decimal strings only)."""

    def boom(s: str) -> None:
        raise AssertionError(f"float in output: {s}")

    json.loads(json.dumps(obj), parse_float=boom)
