#!/usr/bin/env python3
"""Validate packages/contracts (SH-02). Run: make contracts-check
(= uv run --with jsonschema==4.26.0 --with pyyaml==6.0.3 python scripts/contracts_check.py)

  contracts_check.py [--root packages/contracts]
Checks: every *.schema.json is valid JSON Schema 2020-12 with a versioned $id; every examples/**.json names its
schema in "x-validates" and validates (examples/invalid/** must FAIL); no JSON `number` anywhere (golden rule 3:
money/quantity/price/FX are decimal strings); no truth-named property outside a schema marked "x-privileged"
(golden rule 4); VERSION is semver. Exit 1 with one line per problem.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator  # pyright: ignore[reportMissingImports]
from jsonschema.exceptions import SchemaError  # pyright: ignore[reportMissingImports]
from referencing import Registry, Resource  # pyright: ignore[reportMissingImports]

ROOT = Path(__file__).resolve().parents[1]
ID_BASE = "https://secondline.invalid/contracts/1/"
TRUTH_NAMES = re.compile(r"^(truth|truth_ref|root_cause|expected_state_delta|oracle_.*)$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def walk(node, path=""):
    """Yield (json_path, key, value) for every dict entry in a schema tree."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield path, k, v
            yield from walk(v, f"{path}/{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{path}/{i}")


def check(root: Path) -> list[str]:
    problems: list[str] = []
    version = (root / "VERSION").read_text().strip() if (root / "VERSION").exists() else ""
    if not SEMVER.match(version):
        problems.append(f"VERSION: {version!r} is not semver")

    schemas: dict[str, dict] = {}
    for f in sorted(root.rglob("*.schema.json")):
        rel = f.relative_to(root).as_posix()
        try:
            doc = json.loads(f.read_text())
            Draft202012Validator.check_schema(doc)
        except (json.JSONDecodeError, SchemaError) as e:
            problems.append(f"{rel}: invalid schema: {str(e).splitlines()[0]}")
            continue
        if doc.get("$id") != ID_BASE + rel:
            problems.append(f"{rel}: $id must be {ID_BASE + rel}")
        for p, k, v in walk(doc):
            if k == "type" and (v == "number" or (isinstance(v, list) and "number" in v)):
                problems.append(f"{rel}{p}: JSON number is float money/quantity; use common decimal string")
            if k == "properties" and isinstance(v, dict) and not doc.get("x-privileged"):
                for name in v:
                    if TRUTH_NAMES.match(name):
                        problems.append(f"{rel}{p}/properties/{name}: truth field outside an x-privileged schema")
        schemas[rel] = doc

    registry = Registry().with_resources(
        (d["$id"], Resource.from_contents(d)) for d in schemas.values() if "$id" in d)
    docs = sorted((root / "examples").rglob("*.json")) if (root / "examples").exists() else []
    docs += [root / "errors.json"] if (root / "errors.json").exists() else []
    for f in docs:
        rel = f.relative_to(root).as_posix()
        doc = json.loads(f.read_text())
        target = doc.pop("x-validates", None) if isinstance(doc, dict) else None
        file, _, fragment = str(target).partition("#")
        if file not in schemas or "$id" not in schemas[file]:
            problems.append(f"{rel}: x-validates must name a schema in this tree (got {target!r})")
            continue
        # A fragment (common.schema.json#/$defs/x) validates against that one definition.
        schema = {"$ref": schemas[file]["$id"] + "#" + fragment} if fragment else schemas[file]
        errors = list(Draft202012Validator(schema, registry=registry).iter_errors(doc))
        if rel.startswith("examples/invalid/"):
            if not errors:
                problems.append(f"{rel}: expected to be INVALID against {target} but it validates")
        elif errors:
            problems.append(f"{rel}: invalid against {target}: {errors[0].message[:160]}")
    return problems


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="contracts_check.py")
    ap.add_argument("--root", default=str(ROOT / "packages/contracts"))
    a = ap.parse_args(argv)
    problems = check(Path(a.root))
    for p in problems:
        print(p)
    print("contracts OK" if not problems else f"{len(problems)} contract problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
