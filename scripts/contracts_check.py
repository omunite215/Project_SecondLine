#!/usr/bin/env python3
"""Validate packages/contracts (SH-02). Run: make contracts-check
(= uv run --with jsonschema==4.26.0 --with pyyaml==6.0.3 python scripts/contracts_check.py)

  contracts_check.py [--root packages/contracts]
Checks: every *.schema.json is valid JSON Schema 2020-12 with a versioned $id; every examples/**.json names its
schema in "x-validates" and validates (examples/invalid/** must FAIL); no JSON `number` anywhere (golden rule 3:
money/quantity/price/FX are decimal strings); no truth-named property outside a schema marked "x-privileged"
(golden rule 4); VERSION is semver. openapi/*.yaml: 3.1, every $ref resolves, every 4xx/5xx
response uses error_response.schema.json, no truth-named property. Exit 1 with one line per problem.
"""
from __future__ import annotations

import argparse
import json
import posixpath
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urljoin

from jsonschema import Draft202012Validator  # pyright: ignore[reportMissingImports]
from jsonschema.exceptions import SchemaError  # pyright: ignore[reportMissingImports]
import yaml  # pyright: ignore[reportMissingModuleSource]
from referencing import Registry, Resource  # pyright: ignore[reportMissingImports]

ROOT = Path(__file__).resolve().parents[1]
ID_BASE = "https://secondline.invalid/contracts/1/"
# Substring, case-insensitive: names, required entries and enum/const values (not prose descriptions).
TRUTH_NAMES = re.compile(r"(?i)(truth|root[_-]?cause|allowed_outcomes|forbidden_outcomes|expected_state_delta|"
                         r"required_evidence_ids|oracle|canary|break_(type|kind)|injected|hidden)")
CANARY = "SLCANARY-"
CANARY_TOKEN = re.compile(r"SLCANARY-[A-Za-z0-9]+")  # a canary value (any alphanumerics), not prose naming the prefix
# Truth may live only here (ADR-015). A schema can't make itself privileged; visible shapes can't $ref these.
PRIVILEGED = {"scenario/truth.schema.json", "scenario/run_manifest.schema.json", "attacks/attack_pack.schema.json"}
PRIVILEGED_DEFS = {"common.schema.json#/$defs/break_type"}
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
            if doc.get("x-privileged") and rel in PRIVILEGED:
                continue
            exempt = {d.partition("#/$defs/")[2] for d in PRIVILEGED_DEFS if d.startswith(rel + "#")}
            names = [n for n in schema_names(k, v) if not (k == "$defs" and n in exempt)]
            problems += [f"{rel}{p}/{k}: truth field {n!r} outside an x-privileged schema" for n in names
                         if TRUTH_NAMES.search(n)]
            if k in ("$dynamicRef", "$anchor", "$dynamicAnchor") or (k == "$id" and p):
                problems.append(f"{rel}{p}/{k}: not allowed in visible schemas (only plain $ref is resolved and guarded)")
        schemas[rel] = doc

    for rel, doc in schemas.items():
        if doc.get("x-privileged") and rel not in PRIVILEGED:
            problems.append(f"{rel}: x-privileged but not on the privileged list (scripts/contracts_check.py PRIVILEGED)")
        if not (doc.get("x-privileged") and rel in PRIVILEGED):
            problems += [f"{rel}: {m}" for m in privileged_refs(rel, doc)]
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
    problems += check_openapi(root, schemas)
    problems += check_canaries(root, schemas)
    problems += check_action_digest(schemas)
    return problems


def check_action_digest(schemas: dict[str, dict]) -> list[str]:
    """x-action-digest (ADR-011, OM-02): the Java library and the audit-verifier digest exactly these
    fields, so each must be a required property, listed once; sort keys must name included fields."""
    problems = []
    for rel, doc in schemas.items():
        ann = doc.get("x-action-digest")
        if ann is None:
            continue
        include, sort = ann.get("include"), ann.get("sort", {})
        if not isinstance(include, list) or not include or len(set(include)) != len(include):
            problems.append(f"{rel}: x-action-digest.include must be a non-empty list without duplicates")
            continue
        required, props = set(doc.get("required", [])), doc.get("properties", {})
        problems += [f"{rel}: x-action-digest.include {f!r} is not a required property" for f in include
                     if f not in props or f not in required]
        if not isinstance(sort, dict):
            problems.append(f"{rel}: x-action-digest.sort must be an object")
            continue
        problems += [f"{rel}: x-action-digest.sort {f!r} is not in include" for f in sort if f not in include]
    return problems


def schema_names(k: str, v) -> list[str]:
    """Names and values a schema/API keyword can carry that would expose truth: property-like keys
    (properties, patternProperties, dependentSchemas, dependentRequired, $defs), required entries,
    dependentRequired targets, enum and const values. Prose (description, title) is not scanned."""
    names: list[str] = []
    if k in ("properties", "patternProperties", "dependentSchemas", "dependentRequired", "$defs") and isinstance(v, dict):
        names += list(v)
    if k == "dependentRequired" and isinstance(v, dict):
        names += [x for xs in v.values() if isinstance(xs, list) for x in xs if isinstance(x, str)]
    if k in ("required", "enum") and isinstance(v, list):
        names += [x for x in v if isinstance(x, str)]
    if k == "const" and isinstance(v, str):
        names.append(v)
    return names


def privileged_refs(rel: str, doc) -> list[str]:
    """$refs from a visible schema/API that reach a privileged schema or definition. Resolved like the validator
    (urljoin against $id, percent-decoded, normalised, JSON-pointer unescaped); anything outside the tree fails."""
    out = []
    base = (doc.get("$id") if isinstance(doc, dict) else None) or ID_BASE + rel
    for p, k, v in walk(doc):
        if k != "$ref" or not isinstance(v, str):
            continue
        absolute, _, frag = urljoin(base, v).partition("#")
        if not absolute.startswith(ID_BASE):
            out.append(f"{p}: $ref {v} resolves outside the contracts tree")
            continue
        target = posixpath.normpath(unquote(absolute[len(ID_BASE):]))
        if target.startswith(".."):
            out.append(f"{p}: $ref {v} resolves outside the contracts tree")
            continue
        pointer = "/".join(tok.replace("~1", "/").replace("~0", "~") for tok in unquote(frag).split("/"))
        hit = target in PRIVILEGED or any(
            target == f and (pointer == ptr or pointer.startswith(ptr + "/"))
            for f, _, ptr in (d.partition("#") for d in PRIVILEGED_DEFS))
        if hit:
            out.append(f"{p}: visible shape refs privileged {v}")
    return out


def check_canaries(root: Path, schemas: dict[str, dict]) -> list[str]:
    """SLCANARY- may appear only where truth lives (ADR-015): x-privileged schemas, examples of them,
    examples/invalid/** (they prove rejection) and `pattern` values that forbid it. Anywhere else fails."""
    privileged = {rel for rel, d in schemas.items() if d.get("x-privileged") and rel in PRIVILEGED}
    problems = []
    for f in sorted(root.rglob("*")):
        if not f.is_file() or f.suffix not in (".json", ".yaml") or CANARY not in f.read_text():
            continue
        rel = f.relative_to(root).as_posix()
        if rel in privileged or rel.startswith("examples/invalid/"):
            continue
        doc = yaml.safe_load(f.read_text())
        if rel.startswith("examples/") and isinstance(doc, dict) and \
                str(doc.get("x-validates", "")).partition("#")[0] in privileged:
            continue
        # Only a `not: {pattern}` (a rule forbidding the canary) may contain it.
        hits = [p for p, k, v in walk(doc) if isinstance(v, str) and CANARY_TOKEN.search(v)
                and not (k == "pattern" and p.endswith("/not"))]
        hits += [p for p, _, v in walk(doc) if isinstance(v, list) for x in v if isinstance(x, str) and CANARY_TOKEN.search(x)]
        problems += [f"{rel}{p}: contains a {CANARY} truth canary outside a privileged shape" for p in hits]
    return problems


def check_openapi(root: Path, schemas: dict[str, dict]) -> list[str]:
    problems: list[str] = []
    for f in sorted((root / "openapi").glob("*.yaml")) if (root / "openapi").exists() else []:
        rel = f.relative_to(root).as_posix()
        try:
            api = yaml.safe_load(f.read_text())
        except yaml.YAMLError as e:
            problems.append(f"{rel}: invalid YAML: {str(e).splitlines()[0]}")
            continue
        problems += [f"{rel}: {m}" for m in privileged_refs(rel, api)]
        if not str(api.get("openapi", "")).startswith("3.1"):
            problems.append(f"{rel}: openapi must be 3.1.x")
        for p, k, v in walk(api):
            if k == "$ref" and isinstance(v, str) and not v.startswith("#"):
                target, _, frag = v.partition("#")
                target = (f.parent / target).resolve().relative_to(root.resolve()).as_posix() if target else ""
                if target not in schemas:
                    problems.append(f"{rel}{p}: unresolved $ref {v}")
            names = schema_names(k, v) + ([v] if k == "name" and isinstance(v, str) else [])
            problems += [f"{rel}{p}/{k}: truth field {n!r} in an API" for n in names if TRUTH_NAMES.search(n)]
        for path, ops in (api.get("paths") or {}).items():
            for method, op in (ops or {}).items():
                for code, resp in ((op or {}).get("responses") or {}).items():
                    if str(code)[0] in "45":
                        comp = str(resp.get("$ref", "")) if isinstance(resp, dict) else ""
                        if comp.startswith("#/components/responses/"):  # follow one reusable response
                            resp = ((api.get("components") or {}).get("responses") or {}).get(comp.rsplit("/", 1)[1], {})
                        refs = [r for _, k, r in walk(resp) if k == "$ref"]
                        if not any(str(r).endswith("error_response.schema.json") for r in refs):
                            problems.append(f"{rel} {method.upper()} {path} {code}: error response must use error_response.schema.json")
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
