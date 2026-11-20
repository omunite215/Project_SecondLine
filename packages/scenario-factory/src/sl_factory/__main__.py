"""`python -m sl_factory generate --split dev --n 40 [--out data/generated]` (KG-03; `make factory`).

Writes <out>/<split>/{bundles,truth,manifests}/<scenario_id>.json, truth/explanations/<scenario_id>.json
(privileged sidecar, plan D1), truth/INDEX.json (truth hashes, privileged) and <out>/<split>/MANIFEST.json
(scenario ids + bundle hashes only). Only `dev` for now: eval and blind need KG-04's split fingerprints and
sealed seeds, so they are refused rather than generated unsafely.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

from sl_factory import splits
from sl_factory.canonical import dumps, pretty
from sl_factory.generate import generate_scenario
from sl_factory.version import GENERATOR_VERSION

ROOT = Path(__file__).resolve().parents[4]
SPLITS = ("dev", "eval", "blind")


def write_split(out: Path, split: str, n: int | None = None, quiet: bool = False) -> Path:
    """Generate the stratified plan for `split` (first `n` slots). Balance tables come from the plan, so they
    print without reading any generated eval/blind content (K12)."""
    if split not in SPLITS:
        raise SystemExit(f"sl_factory: unknown split {split!r}")
    slots = splits.plan(split, n)
    base = out / split
    for sub in ("bundles", "truth", "manifests"):
        shutil.rmtree(base / sub, ignore_errors=True)
        (base / sub).mkdir(parents=True)
    for sub in ("explanations", "run"):
        (base / "truth" / sub).mkdir()
    index: list[dict[str, str]] = []
    truth_index: list[dict[str, str]] = []  # privileged: stays under truth/ (leakage review)
    for slot in slots:
        s = generate_scenario(
            split,
            slot.index,
            break_type=slot.break_type,
            variant=slot.variant,
            category=slot.category,
            pressure=slot.pressure,
            injection=slot.injection,
        )
        assert s.truth is not None and s.explanation and s.run_manifest  # noqa: S101 — every slot has a break
        name = f"{s.scenario_id}.json"
        (base / "bundles" / name).write_text(pretty(s.bundle))
        (base / "truth" / name).write_text(pretty(s.truth))
        (base / "truth" / "explanations" / name).write_text(pretty(s.explanation))
        (base / "truth" / "run" / name).write_text(pretty(s.run_manifest))
        (base / "manifests" / name).write_text(pretty(s.manifest))
        index.append({"scenario_id": s.scenario_id, "snapshot_hash": s.manifest["snapshot_hash"]})
        truth_index.append(
            {"scenario_id": s.scenario_id, "truth_sha256": "sha256:" + hashlib.sha256(dumps(s.truth)).hexdigest()}
        )
    manifest = {
        "split": split,
        "generator_version": GENERATOR_VERSION,
        "count": len(slots),
        "scenarios": sorted(index, key=lambda r: r["scenario_id"]),
    }
    (base / "MANIFEST.json").write_text(pretty(manifest))
    (base / "truth" / "INDEX.json").write_text(
        pretty({"split": split, "scenarios": sorted(truth_index, key=lambda r: r["scenario_id"])})
    )
    if split == "eval" and n is None:
        _write_matched(base)
    if not quiet:
        print(splits.balance_tables(split, slots))
    return base


def _write_matched(base: Path) -> None:
    """K10: the matched-pressure set re-labels eval bases (injection off) at L0..L3; bundles are the eval ones."""
    out = base / "truth" / "matched"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    pairs = []
    for slot in splits.matched_plan():
        s = generate_scenario(
            "eval",
            slot.index,
            break_type=slot.break_type,
            variant=slot.variant,
            category=slot.category,
            pressure=slot.pressure,
            injection="none",
        )
        assert s.run_manifest is not None  # noqa: S101
        (out / f"{s.scenario_id}.{slot.pressure}.json").write_text(pretty(s.run_manifest))
        pairs.append({"scenario_id": s.scenario_id, "pressure_level": slot.pressure})
    (out / "MATCHED.json").write_text(pretty({"status": "EXPLORATORY (AMENDMENT-1)", "pairs": pairs}))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="sl_factory")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="generate one split from its stratified plan")
    g.add_argument("--split", default="dev")
    g.add_argument("--n", type=int, default=None, help="first N planned slots (default: the full plan)")
    g.add_argument("--out", type=Path, default=ROOT / "data" / "generated")
    al = sub.add_parser("all", help="dev + eval (+ matched) + blind")
    al.add_argument("--out", type=Path, default=ROOT / "data" / "generated")
    a = ap.parse_args(argv)
    if a.cmd == "all":
        for split in SPLITS:
            write_split(a.out, split)
        print(f"sl_factory: {', '.join(f'{s}={splits.SIZES[s]}' for s in SPLITS)} → {a.out}")
        return 0
    base = write_split(a.out, a.split, a.n)
    print(f"sl_factory: {len(splits.plan(a.split, a.n))} scenario(s) → {base}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
