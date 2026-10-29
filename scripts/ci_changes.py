#!/usr/bin/env python3
"""Which CI jobs a change needs (OM-01, stdlib only).

Path filtering lives here, not on workflow triggers: a trigger-filtered workflow never reports, so a
required check would block every PR it skips. Jobs gate on `needs.changes.outputs.<job> == 'true'` and
report "skipped" (which satisfies a required check) when false.

  ci_changes.py --base SHA --head SHA     prints `lint=true`, `java=…`, `stack=…` (append to $GITHUB_OUTPUT)
Fail closed: a git error or an empty diff runs every job.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path

JOBS: dict[str, tuple[str, ...]] = {
    "java": ("services/ledger/*", "services/gateway/*", "libs/contracts-java/*", "build.gradle.kts",
             "settings.gradle.kts", "gradle.properties", "gradle/*", "gradlew*", "packages/contracts/*"),
    # stack builds the Java images and mounts infra configs, so it also runs for everything java does.
    "stack": ("infra/*", "services/ledger/*", "services/gateway/*", "libs/contracts-java/*", "build.gradle.kts",
              "settings.gradle.kts", "gradle.properties", "gradle/*", "gradlew*", ".dockerignore", ".env.example",
              "Makefile", "scripts/bootstrap_env.py", "tests/infra/*"),
}
RUN_ALL = (".github/workflows/*", "scripts/ci_changes.py")


def classify(paths: list[str]) -> dict[str, bool]:
    if not paths or any(fnmatch(p, g) for p in paths for g in RUN_ALL):
        return {"lint": True, **{job: True for job in JOBS}}
    return {"lint": True, **{job: any(fnmatch(p, g) for p in paths for g in globs) for job, globs in JOBS.items()}}


REF = re.compile(r"[0-9a-fA-F]{7,40}|HEAD|[A-Za-z0-9][\w./-]*")  # never starts with "-"


def changed(base: str, head: str, cwd: Path | None = None) -> list[str]:
    """Paths touched between base and head, both sides of renames, NUL-separated so no name is mangled.
    Any error (bad ref, option-like ref, git failure) → [] → classify() runs every job."""
    if not (REF.fullmatch(base) and REF.fullmatch(head)):
        print(f"ci_changes: refusing ref {base!r}/{head!r}; running every job", file=sys.stderr)
        return []
    r = subprocess.run(["git", "-c", "core.quotePath=false", "diff", "--name-only", "-z", "--no-renames",
                        "--end-of-options", f"{base}...{head}"], capture_output=True, cwd=cwd)
    if r.returncode != 0:
        print(f"ci_changes: git diff failed ({r.stderr.decode(errors='replace').strip()[:200]}); running every job",
              file=sys.stderr)
        return []
    return [p for p in r.stdout.decode("utf-8", errors="surrogateescape").split("\0") if p]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="ci_changes.py")
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", required=True)
    a = ap.parse_args(argv)
    for job, run in classify(changed(a.base, a.head)).items():
        print(f"{job}={'true' if run else 'false'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
