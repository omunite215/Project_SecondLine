"""Seeded randomness, opaque ids and canaries (KG-03, ADR-015).

Every random draw comes from a named sub-stream derived from the scenario seed, so adding a draw in one place
never shifts another. No wall clock, no global `random`, no hash() of str (PYTHONHASHSEED-dependent).
"""

from __future__ import annotations

import hashlib
import random
import re
from collections.abc import Callable

from sl_factory.version import GENERATOR_VERSION

FORBIDDEN = re.compile(r"(dev|eval|blind|test)", re.IGNORECASE)  # an id must never reveal a split (ADR-015)
_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
_ID_BODY = 12


def _int(label: str) -> int:
    return int.from_bytes(hashlib.sha256(label.encode()).digest()[:8], "big")


def derive_seed(split: str, index: int) -> int:
    """Scenario seed from split + index + generator version (plan D5); 32-bit (run_manifest `seed` contract)."""
    return _int(f"{split}:{index}:{GENERATOR_VERSION}") >> 32


class Streams:
    def __init__(self, seed: int) -> None:
        self.seed = seed

    def stream(self, label: str) -> random.Random:
        return random.Random(_int(f"{self.seed}:{label}"))


class IdMinter:
    """Opaque `<prefix>_<12 base62>` ids, unique per scenario; redraws any draw that spells a split name."""

    def __init__(self, rng: random.Random, draw: Callable[[], str] | None = None) -> None:
        self._rng = rng
        self._draw = draw or self._default_draw
        self._used: set[str] = set()

    def _default_draw(self) -> str:
        return "".join(self._rng.choice(_ALPHABET) for _ in range(_ID_BODY))

    def mint(self, prefix: str) -> str:
        while True:
            ident = f"{prefix}_{self._draw()}"
            if FORBIDDEN.search(ident) or ident in self._used:
                continue
            self._used.add(ident)
            return ident


def make_canary(rng: random.Random) -> str:
    return "SLCANARY-" + "".join(rng.choice("0123456789abcdef") for _ in range(32))
