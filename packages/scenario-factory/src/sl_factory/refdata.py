"""The factory's only reader of data/reference (KG-02, §6, SEC-14): every file is looked up in MANIFEST.json and
its sha256 checked before use, so an unlisted, swapped or edited snapshot fails loudly instead of feeding a
world. Snapshots are written by scripts/refdata.py; KG-04 (B4 FX, B7 codes, B8 LEIs) is the first consumer.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

REF_ROOT = Path(__file__).resolve().parents[4] / "data" / "reference"


class RefdataError(RuntimeError):
    pass


def _manifest(root: Path) -> dict[str, Any]:
    p = root / "MANIFEST.json"
    if not p.is_file():
        raise RefdataError(f"no reference MANIFEST at {p} (run `make refdata-fetch`)")
    doc: dict[str, Any] = json.loads(p.read_text())
    return doc


def refs(root: Path = REF_ROOT) -> list[str]:
    return sorted(s["ref"] for s in _manifest(root)["snapshots"])


def snapshot(ref: str, name: str, root: Path = REF_ROOT) -> Any:
    """Parsed JSON of file `name` in snapshot `ref` (e.g. "ecb@2026-11-20", "rates.json"), hash-verified."""
    snap = next((s for s in _manifest(root)["snapshots"] if s["ref"] == ref), None)
    if snap is None:
        raise RefdataError(f"snapshot {ref!r} is not in MANIFEST")
    entry = next((f for f in snap["files"] if f["path"] == f"{snap['source']}/{snap['date']}/{name}"), None)
    if entry is None:
        raise RefdataError(f"{name!r} is not listed under {ref!r}")
    data = (root / entry["path"]).read_bytes()
    if "sha256:" + hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise RefdataError(f"{entry['path']}: sha256 mismatch")
    return json.loads(data)
