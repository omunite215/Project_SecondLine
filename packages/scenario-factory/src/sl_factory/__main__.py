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

from sl_factory.canonical import dumps, pretty
from sl_factory.generate import generate_scenario
from sl_factory.version import GENERATOR_VERSION

ROOT = Path(__file__).resolve().parents[4]
SUPPORTED_SPLITS = ("dev",)


def write_split(out: Path, split: str, n: int) -> Path:
    if split not in SUPPORTED_SPLITS:
        raise SystemExit(f"sl_factory: split {split!r} arrives with KG-04 (split fingerprints, sealed seeds)")
    base = out / split
    for sub in ("bundles", "truth", "manifests"):
        shutil.rmtree(base / sub, ignore_errors=True)
        (base / sub).mkdir(parents=True)
    (base / "truth" / "explanations").mkdir()
    index: list[dict[str, str]] = []
    truth_index: list[dict[str, str]] = []  # privileged: stays under truth/ (leakage review)
    for i in range(n):
        s = generate_scenario(split, i)
        assert s.truth is not None and s.explanation is not None  # noqa: S101 — every indexed scenario has a break
        name = f"{s.scenario_id}.json"
        (base / "bundles" / name).write_text(pretty(s.bundle))
        (base / "truth" / name).write_text(pretty(s.truth))
        (base / "truth" / "explanations" / name).write_text(pretty(s.explanation))
        (base / "manifests" / name).write_text(pretty(s.manifest))
        index.append({"scenario_id": s.scenario_id, "snapshot_hash": s.manifest["snapshot_hash"]})
        truth_index.append(
            {"scenario_id": s.scenario_id, "truth_sha256": "sha256:" + hashlib.sha256(dumps(s.truth)).hexdigest()}
        )
    manifest = {
        "split": split,
        "generator_version": GENERATOR_VERSION,
        "count": n,
        "scenarios": sorted(index, key=lambda r: r["scenario_id"]),
    }
    (base / "MANIFEST.json").write_text(pretty(manifest))
    truth_manifest = {"split": split, "scenarios": sorted(truth_index, key=lambda r: r["scenario_id"])}
    (base / "truth" / "INDEX.json").write_text(pretty(truth_manifest))
    return base


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="sl_factory")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="generate a split")
    g.add_argument("--split", default="dev")
    g.add_argument("--n", type=int, default=40)
    g.add_argument("--out", type=Path, default=ROOT / "data" / "generated")
    a = ap.parse_args(argv)
    base = write_split(a.out, a.split, a.n)
    print(f"sl_factory: {a.n} scenario(s) → {base}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
