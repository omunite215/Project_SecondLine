#!/usr/bin/env python3
"""Leakage, split-integrity and canary checks (KG-05; §5 §6 §15, REQ-006, T-DOM-03 T-SEC-06, SEC-11, RSK-11).

Rules, each over agent-visible surfaces only (privileged code and truth are allowed to contain truth):
  canary            a real canary (collected from data/generated/*/truth) or any `SLCANARY-` string
  truth-field       a truth field name or a B1–B8 label used on an agent-visible surface
  import            `sl_factory` / `sl_eval` imported outside packages/scenario-factory and packages/evaluation
  opaque-id         an id in a visible bundle/manifest that isn't `<prefix>_<base62>` or spells a split
  split-overlap     the same scenario content (ids, dates, amounts masked) in dev and in eval/blind
  template-overlap  a `template_id` (KG-04 sidecars) shared by dev and eval/blind

Findings print as `LEAK <rule> <path>[:<line>]` and never include the matched text, so the scan can't itself
leak a canary or a truth value into CI logs. Exit 1 on any finding. Stdlib only.
usage: leakage.py [--root DIR]
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

# Agent-visible surfaces (§7 boundary): everything the agent, MCP adapter, gateway, ledger, supervisor or console
# can show, plus recorded runs. Privileged trees are simply not listed.
VISIBLE = [
    "services/agent",
    "services/mcp-adapter",
    "services/supervisor",
    "services/gateway",
    "services/ledger",
    "apps/console",
    "infra/opa",
    "experiments/runs",
    "data/attacks",
]
VISIBLE_DATA = ("bundles", "manifests")  # under data/generated/<split>/
SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", ".gradle", "build", ".mypy_cache", ".ruff_cache",
             ".pytest_cache", "target"}
SKIP_NAMES = {"CLAUDE.md"}  # Claude's own area notes, never served to the agent
PRIVILEGED_PACKAGES = ("packages/scenario-factory", "packages/evaluation")
SPLITS_SEALED = ("eval", "blind")

CANARY_RE = re.compile(r"SLCANARY-")
TRUTH_FIELDS = ("root_cause", "allowed_outcomes", "forbidden_outcomes", "expected_state_delta",
                "required_evidence_ids", "causal_event_ids", "truth_ref", "break_type",
                "escalation_if_insufficient_evidence", "scenario_generator_version")
TRUTH_RE = re.compile(r"\b(" + "|".join(TRUTH_FIELDS) + r")\b|\bB[1-8]_[A-Z][A-Z_]+\b")
IMPORT_RE = re.compile(r"^\s*(from|import)\s+(sl_factory|sl_eval)\b", re.M)
OPAQUE_RE = re.compile(r"^[a-z]{2,6}_[0-9A-Za-z]{8,32}$")
SPLIT_WORD = re.compile(r"(dev|eval|blind|test)", re.I)
ID_KEY = re.compile(r"(_id|_ids|_ref)$")
MASKS = [
    (re.compile(r"\b[a-z]{2,6}_[0-9A-Za-z]{8,32}\b"), "<id>"),
    (re.compile(r"\b[A-Z]{2}[A-Z0-9]{9}[0-9]\b"), "<isin>"),
    (re.compile(r"\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}(\.\d+)?Z)?"), "<t>"),
    (re.compile(r"-?\d+(\.\d+)?"), "<n>"),
]


class Scan:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.findings: list[str] = []

    def hit(self, rule: str, path: Path, line: int | None = None) -> None:
        where = path.relative_to(self.root).as_posix() + (f":{line}" if line else "")
        self.findings.append(f"LEAK {rule} {where}")

    # ---- inputs ------------------------------------------------------------------------------------------
    def files(self, rel: str) -> Iterator[Path]:
        base = self.root / rel
        if not base.exists():
            return
        for p in sorted(base.rglob("*")):
            if p.is_file() and not (set(p.relative_to(self.root).parts) & SKIP_DIRS) and p.name not in SKIP_NAMES:
                yield p

    def visible_files(self) -> Iterator[Path]:
        for rel in VISIBLE:
            yield from self.files(rel)
        for split_dir in sorted((self.root / "data" / "generated").glob("*")):
            for sub in VISIBLE_DATA:
                yield from self.files((split_dir / sub).relative_to(self.root).as_posix())

    def canaries(self) -> set[str]:
        found: set[str] = set()
        for p in sorted((self.root / "data" / "generated").glob("*/truth/*.json")):
            doc = _load(p)
            if isinstance(doc, dict) and isinstance(doc.get("canary"), str):
                found.add(doc["canary"])
        return found

    # ---- rules -------------------------------------------------------------------------------------------
    def text_rules(self) -> None:
        canaries = self.canaries()
        for p in self.visible_files():
            text = _text(p)
            if text is None:
                continue
            for n, line in enumerate(text.splitlines(), 1):
                if CANARY_RE.search(line) or any(c in line for c in canaries):
                    self.hit("canary", p, n)
                if TRUTH_RE.search(line):
                    self.hit("truth-field", p, n)

    def import_rule(self) -> None:
        for p in sorted(self.root.rglob("*.py")):
            rel = p.relative_to(self.root).as_posix()
            if set(p.relative_to(self.root).parts) & SKIP_DIRS or rel.startswith(PRIVILEGED_PACKAGES):
                continue
            if not (rel.startswith(("services/", "apps/", "packages/"))):
                continue  # scripts/ and tests/ may import the factory to test it
            text = _text(p) or ""
            if not IMPORT_RE.search(text):
                continue
            try:
                tree = ast.parse(text)
            except SyntaxError:
                self.hit("import", p)
                continue
            for node in ast.walk(tree):
                mods = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                    [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
                if any(m.split(".")[0] in ("sl_factory", "sl_eval") for m in mods):
                    self.hit("import", p, node.lineno)

    def opaque_rule(self) -> None:
        for split_dir in sorted((self.root / "data" / "generated").glob("*")):
            for sub in VISIBLE_DATA:
                for p in self.files((split_dir / sub).relative_to(self.root).as_posix()):
                    if p.suffix == ".json" and not _ids_opaque(_load(p)):
                        self.hit("opaque-id", p)

    def overlap_rules(self) -> None:
        gen = self.root / "data" / "generated"
        prints: dict[str, dict[str, Path]] = {}
        templates: dict[str, dict[str, Path]] = {}
        for split_dir in sorted(p for p in gen.glob("*") if p.is_dir()):
            split = split_dir.name
            prints[split] = {_fingerprint(_load(p)): p for p in sorted((split_dir / "bundles").glob("*.json"))}
            templates[split] = {}
            for p in sorted((split_dir / "truth" / "explanations").glob("*.json")):
                doc = _load(p)
                if isinstance(doc, dict) and isinstance(doc.get("template_id"), str):
                    templates[split][doc["template_id"]] = p
        for sealed in SPLITS_SEALED:
            for fp, p in prints.get(sealed, {}).items():
                if fp in prints.get("dev", {}):
                    self.hit("split-overlap", p)
            for tid, p in templates.get(sealed, {}).items():
                if tid in templates.get("dev", {}):
                    self.hit("template-overlap", p)

    def run(self) -> list[str]:
        self.text_rules()
        self.import_rule()
        self.opaque_rule()
        self.overlap_rules()
        return self.findings


def _text(p: Path) -> str | None:
    try:
        return p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None  # binary: no text surface


def _load(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def _ids_opaque(doc: Any, key: str = "") -> bool:
    if isinstance(doc, dict):
        return all(_ids_opaque(v, k) for k, v in doc.items())
    if isinstance(doc, list):
        return all(_ids_opaque(v, key) for v in doc)
    if isinstance(doc, str) and ID_KEY.search(key) and key not in ("initial_state_ref",):
        return bool(OPAQUE_RE.match(doc)) and not SPLIT_WORD.search(doc)
    return True


def _fingerprint(doc: Any) -> str:
    text = json.dumps(doc, sort_keys=True, separators=(",", ":"))
    for rx, repl in MASKS:
        text = rx.sub(repl, text)
    return hashlib.sha256(text.encode()).hexdigest()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    a = ap.parse_args(argv)
    findings = Scan(a.root.resolve()).run()
    for f in findings:
        print(f)
    print(f"leakage-check: {len(findings)} finding(s)" if findings else "leakage-check: clean")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
