"""Canonical bytes + sha256 for factory outputs (KG-03: same seed ⇒ same bytes ⇒ same hash).

Sorted keys, compact separators, UTF-8. Values are only strings, ints, bools, lists and objects (decimals are
strings, golden rule 3), so this equals RFC 8785 JCS for our documents; a float is rejected outright.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _reject_floats(obj: Any) -> None:
    if isinstance(obj, float):
        raise TypeError(f"float in factory output: {obj!r} (use a decimal string)")
    if isinstance(obj, dict):
        for v in obj.values():
            _reject_floats(v)
    elif isinstance(obj, list):
        for v in obj:
            _reject_floats(v)


def dumps(obj: Any) -> bytes:
    _reject_floats(obj)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256_ref(obj: Any) -> str:
    return "sha256:" + hashlib.sha256(dumps(obj)).hexdigest()


def pretty(obj: Any) -> str:
    """Stable on-disk form (sorted, indented); hashes are always taken over `dumps`, not this."""
    _reject_floats(obj)
    return json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=False) + "\n"
