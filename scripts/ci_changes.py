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
import subprocess
import sys
from fnmatch import fnmatch

JOBS: dict[str, tuple[str, ...]] = {
    "java": ("services/ledger/*", "services/gateway/*", "libs/contracts-java/*", "build.gradle.kts",
             "settings.gradle.kts", "gradle.properties", "gradle/*", "gradlew*", "packages/contracts/*"),
    "stack": ("infra/compose/*", "infra/db/*", "infra/opa/*", "services/*/Dockerfile", ".dockerignore",
              ".env.example", "Makefile", "scripts/bootstrap_env.py", "tests/infra/*"),
}
RUN_ALL = (".github/workflows/*", "scripts/ci_changes.py")


def classify(paths: list[str]) -> dict[str, bool]:
    if not paths or any(fnmatch(p, g) for p in paths for g in RUN_ALL):
        return {"lint": True, **{job: True for job in JOBS}}
    return {"lint": True, **{job: any(fnmatch(p, g) for p in paths for g in globs) for job, globs in JOBS.items()}}


def changed(base: str, head: str) -> list[str]:
    r = subprocess.run(["git", "diff", "--name-only", f"{base}...{head}"], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"ci_changes: git diff failed ({r.stderr.strip()[:200]}); running every job", file=sys.stderr)
        return []
    return r.stdout.split()


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
