#!/usr/bin/env python3
"""PostToolUse (Edit|Write) formatter: formats the edited file when its formatter is installed.
Silent, always exits 0. Saves tokens: no format/lint fix-up round trips later."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SKIP = ("/docs/spec/", "/node_modules/", "/build/", "/_generated/", "/experiments/prereg/frozen/", "/.venv/")


def run(cmd: list[str]) -> None:
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25, check=False)
    except Exception:
        pass


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    p = Path(str((data.get("tool_input") or {}).get("file_path") or ""))
    s = str(p).replace("\\", "/")
    if not p.is_file() or any(x in s for x in SKIP):
        return 0
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or ".")
    ext = p.suffix.lower()
    if ext == ".py" and shutil.which("ruff"):
        run(["ruff", "format", "-q", s])
        run(["ruff", "check", "-q", "--select", "I", "--fix", s])
    elif ext in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".css", ".json") and "/apps/console/" in s:
        prettier = root / "apps/console/node_modules/.bin/prettier"
        if prettier.exists():
            run([str(prettier), "--write", "--log-level", "silent", s])
    elif ext == ".java" and shutil.which("google-java-format"):
        run(["google-java-format", "--replace", s])
    elif ext == ".rego" and shutil.which("opa"):
        run(["opa", "fmt", "-w", s])
    return 0


if __name__ == "__main__":
    sys.exit(main())
