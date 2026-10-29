#!/usr/bin/env python3
"""Create the local .env with random secrets (OM-01, stdlib only). Never overwrites; never prints secrets.

  bootstrap_env.py [--path .env]
Keys come from .env.example; every empty value there is a secret generated here.
"""
from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="bootstrap_env.py")
    ap.add_argument("--path", default=str(ROOT / ".env"))
    a = ap.parse_args(argv)
    path = Path(a.path)
    if path.exists():
        print(f"{path}: exists, left unchanged")
        return 0
    lines = []
    for line in (ROOT / ".env.example").read_text().splitlines():
        key, sep, value = line.partition("=")
        if sep and not line.startswith("#") and value == "":
            value = secrets.token_urlsafe(24)
        lines.append(f"{key}{sep}{value}" if sep else line)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"{path}: created with random secrets (mode 600)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
