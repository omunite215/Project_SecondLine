#!/usr/bin/env python3
"""Submission rubric check (OM-27, T-DOC-01, NFR-11; stdlib only).

Maps the course's Signature Assessment rubric onto executable checks so "is this submittable?" has evidence,
not opinion. Every check is PASS/FAIL with the files or targets behind it; the band per criterion is an
ESTIMATE from the pass ratio, not a grade.

  submission_check.py [--root .]                     static checks (seconds)
  submission_check.py --deploy [--ref BRANCH]        + fresh clone → make bootstrap → up core → test → down
Exit 1 when any check fails.

Criteria (rubric points): Code organization 20 · Technical documentation 20 · Code quality 15 ·
Completeness 20 · Deployment and reproducibility 25.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRITERIA = {"O": ("Code organization", 20), "D": ("Technical documentation", 20), "Q": ("Code quality", 15),
            "P": ("Completeness", 20), "R": ("Deployment and reproducibility", 25)}
SKIP = {".git", "build", ".gradle", "node_modules", ".venv", ".next", "__pycache__", "_generated", ".superpowers",
        ".mypy_cache", ".ruff_cache", ".pytest_cache"}
SKIP_PATHS = ("data/generated", "experiments/runs")
ROOT_FILES = {"README.md", "START_HERE.md", "CLAUDE.md", "LICENSE", "Makefile", ".gitignore", ".gitattributes",
              ".dockerignore", ".env.example", ".pre-commit-config.yaml", ".python-version", "pyproject.toml",
              "uv.lock", "settings.gradle.kts", "build.gradle.kts", "gradle.properties", "gradlew", "gradlew.bat",
              "CLAUDE.local.md.om.example", "CLAUDE.local.md.kunal.example"}
ROOT_LOCAL = {".env", "CLAUDE.local.md"}  # gitignored, personal: allowed on disk, never required
COMPONENT_PARENTS = ("apps/", "services/", "packages/", "libs/")
CODE_SUFFIXES = {".py", ".java", ".kt", ".ts", ".tsx", ".js", ".go", ".rego", ".sql", ".sh"}
# Only in a comment (#, //, --, /* or *), and only when no (TASK-ID) follows: TODO(OM-04) is traceable.
TODO_RE = re.compile(r"(#|//|--|/\*|^\s*\*)[^\n]*?\b(" + "TO" + "DO|FIX" + r"ME)\b(?!\([A-Z]{2,5}-\d+\))")  # split: no self-match
TODO_TARGET = "$(call todo,"


@dataclass
class Check:
    id: str
    ok: bool
    evidence: str
    title: str = ""


def files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root).as_posix()
        dirnames[:] = [d for d in dirnames if d not in SKIP and not f"{rel_dir}/{d}".lstrip("./").startswith(SKIP_PATHS)]
        for f in filenames:
            yield (Path(dirpath) / f).relative_to(root).as_posix()


def repo_map(root: Path) -> list[str]:
    text = (root / "CLAUDE.md").read_text() if (root / "CLAUDE.md").exists() else ""
    block = re.search(r"## Repo map\s*```text\n(.*?)```", text, re.S)
    return [line.split()[0].rstrip("/") for line in block.group(1).splitlines() if line.strip()] if block else []


def make_targets(root: Path) -> dict[str, bool]:
    """target -> True when it's a TODO stub (prints TODO(<TASK>) and exits 1)."""
    mk = (root / "Makefile").read_text() if (root / "Makefile").exists() else ""
    out: dict[str, bool] = {}
    for m in re.finditer(r"(?m)^([a-z][a-z0-9-]*):(?!=)[^\n]*\n((?:\t[^\n]*\n?)*)", mk):  # not `X := v`
        out[m.group(1)] = TODO_TARGET in m.group(2)
    return out


def human_docs(root: Path, all_files: list[str]) -> list[str]:
    docs = [f for f in ("README.md", "START_HERE.md") if (root / f).exists()]
    docs += [f for f in all_files if f.startswith("docs/setup/") and f.endswith(".md")]
    docs += [f for f in all_files if f.startswith(COMPONENT_PARENTS) and f.endswith("/README.md") and f.count("/") == 2]
    return docs


def components(root: Path) -> list[str]:
    return [d for d in repo_map(root) if d.startswith(COMPONENT_PARENTS) and (root / d).is_dir()]


def run_checks(root: Path, deploy: bool = False, ref: str | None = None) -> list[Check]:
    fs = sorted(files(root))
    checks: list[Check] = []

    def add(cid: str, title: str, bad: list[str], ok_note: str = "", limit: int = 8):
        shown = ", ".join(bad[:limit]) + (f" (+{len(bad) - limit} more)" if len(bad) > limit else "")
        checks.append(Check(cid, not bad, shown if bad else ok_note, title))

    # --- Code organization -------------------------------------------------------------------------------
    rmap = repo_map(root)
    add("O1", "Every directory in the CLAUDE.md repo map exists",
        [d for d in rmap if not (root / d).is_dir()] or ([] if rmap else ["CLAUDE.md has no repo map"]),
        f"{len(rmap)} mapped directories present")
    add("O2", "Root holds only known project files", sorted(
        f for f in fs if "/" not in f and f not in ROOT_FILES and f not in ROOT_LOCAL), "root is clean")
    add("O3", "Every component has a human README.md (not only agent notes)",
        [c for c in components(root) if not (root / c / "README.md").exists()], "all components documented")

    # --- Technical documentation -------------------------------------------------------------------------
    readme = (root / "README.md").read_text() if (root / "README.md").exists() else ""
    quick = re.search(r"(?im)^#+ .*(quickstart|getting started|setup|deploy)", readme)
    add("D1", "README has a quickstart with the exact bootstrap + up commands",
        [] if quick and "make bootstrap" in readme and "make up" in readme else
        ["README.md: no Quickstart section with `make bootstrap` and `make up`"], "quickstart present")
    prereq = re.search(r"(?is)^#+ *prerequisites(.*?)(^#|\Z)", readme, re.M)
    tools = ("docker", "compose", "python", "java")
    missing = [t for t in tools if not prereq or t not in prereq.group(1).lower()]
    add("D2", "README lists prerequisites with versions (Docker/Compose, Python, Java)",
        [f"README.md: prerequisites missing {', '.join(missing)}"] if missing or not re.search(
            r"\d", prereq.group(1) if prereq else "") else [], "prerequisites listed")
    targets = make_targets(root)
    bad_refs = []
    for doc in human_docs(root, fs):
        for t in sorted(set(re.findall(r"`make ([a-z][a-z0-9-]*\*?)", (root / doc).read_text()))):
            if t.endswith(("-", "*")):  # a documented family like `make hpc-*`: any implemented member counts
                if not any(n.startswith(t.rstrip("*")) and not todo for n, todo in targets.items()):
                    bad_refs.append(f"{doc}: make {t} (no implemented member)")
            elif t not in targets:
                bad_refs.append(f"{doc}: make {t} (missing)")
            elif targets[t]:
                bad_refs.append(f"{doc}: make {t} (TODO stub)")
    add("D3", "Every `make` command in human docs exists and is implemented", bad_refs, "all documented commands real")
    env_keys = set(re.findall(r"(?m)^([A-Z][A-Z0-9_]*)=", (root / ".env.example").read_text())) \
        if (root / ".env.example").exists() else set()
    compose_vars = {v for f in fs if f.startswith("infra/compose/") and f.endswith((".yml", ".yaml"))
                    for v in re.findall(r"\$\{([A-Z][A-Z0-9_]*)", (root / f).read_text())}
    add("D4", "Every compose variable is declared in .env.example", sorted(compose_vars - env_keys),
        f"{len(compose_vars)} variables declared")

    # --- Code quality ------------------------------------------------------------------------------------
    no_doc = []
    for f in fs:
        if f.startswith("scripts/") and f.endswith(".py"):
            try:
                if not ast.get_docstring(ast.parse((root / f).read_text())):
                    no_doc.append(f)
            except SyntaxError:
                no_doc.append(f"{f} (syntax error)")
    add("Q1", "Every script has a module docstring explaining its purpose", no_doc, "all scripts documented")
    todos = [f"{f}:{i}" for f in fs if Path(f).suffix in CODE_SUFFIXES
             for i, line in enumerate((root / f).read_text(errors="replace").splitlines(), 1) if TODO_RE.search(line)]
    add("Q2", "No TODO/FIXME without a task ID in code", todos, "every TODO is traceable")
    untested = []
    for c in components(root):
        src = [f for f in fs if f.startswith(c + "/") and Path(f).suffix in CODE_SUFFIXES
               and Path(f).name != "__init__.py"]
        tests = [f for f in src if re.search(r"(^|/)(test_[^/]*|[^/]*Test|[^/]*\.test)\.[a-z]+$|/tests?/", f)]
        if src and not tests:
            untested.append(c)
    add("Q3", "Every component with source code has tests next to it", untested, "all components tested")

    # --- Completeness ------------------------------------------------------------------------------------
    stubs = sorted(t for t, todo in targets.items() if todo)
    add("P1", "No make target is still a TODO stub (placeholder)", stubs, "all targets implemented", limit=12)
    add("P2", "No component directory is docs-only (planned but empty)",
        [c for c in components(root) if not [f for f in fs if f.startswith(c + "/") and not f.endswith(".md")]],
        "every component has content")
    placeholders = [f"{d}:{i}" for d in human_docs(root, fs) + [f for f in fs if f == "docs/team/PLAN.md"]
                    for i, line in enumerate((root / d).read_text().splitlines(), 1)
                    if "______" in line or re.search(r"\bTBD\b", line)]
    add("P3", "No placeholder values (______ / TBD) in human-facing docs", placeholders, "no placeholders")
    lock_gaps = []
    if (root / "build.gradle.kts").exists() and not (root / "gradle/wrapper/gradle-wrapper.properties").exists():
        lock_gaps.append("build.gradle.kts without the Gradle wrapper")
    if (root / "pyproject.toml").exists() and not (root / "uv.lock").exists():
        lock_gaps.append("pyproject.toml without uv.lock")
    for f in fs:
        if f.endswith("package.json") and not any((root / Path(f).parent / n).exists()
                                                  for n in ("pnpm-lock.yaml", "package-lock.json")):
            lock_gaps.append(f"{f} without a lockfile")
    add("P4", "Every build file ships its wrapper/lockfile", lock_gaps, "dependencies locked")

    # --- Deployment and reproducibility ------------------------------------------------------------------
    unpinned = []
    for f in fs:
        text = (root / f).read_text(errors="replace") if f.endswith((".yml", ".yaml")) or Path(f).name == "Dockerfile" else ""
        built = set(re.findall(r"(?m)^\s*image:\s*([^\s#]+)\s*\n\s*pull_policy:\s*build", text))  # built here
        for img in re.findall(r"(?m)^\s*(?:image:|FROM)\s+([^\s#]+)", text):
            if img in built:
                continue
            tag = img.rsplit(":", 1)[1] if ":" in img.split("/")[-1] else ""
            if not img.startswith("${") and (not re.search(r"\d", tag) or "latest" in tag):
                unpinned.append(f"{f}: {img}")
        if f.startswith(".github/workflows/"):
            unpinned += [f"{f}: {u}" for u in re.findall(r"uses:\s*([^\s#]+)", text)
                         if not u.startswith(("actions/", "./")) and not re.search(r"@[0-9a-f]{40}$", u)]
    add("R1", "Images and third-party CI actions are pinned to exact versions", unpinned, "everything pinned")
    if deploy:
        checks.append(deploy_check(ref))
    return checks


def deploy_check(ref: str | None) -> Check:
    """Fresh clone of REF → make bootstrap → make up PROFILES=core → make test → down -v, in a temp dir."""
    tmp = Path(tempfile.mkdtemp(prefix="sl-submission-"))
    env = dict(os.environ, COMPOSE_PROJECT_NAME=f"slsub{os.getpid()}")
    url = subprocess.run(["git", "remote", "get-url", "origin"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    steps = [["git", "clone", "-q", "--depth", "1"] + (["--branch", ref] if ref else []) + [url, str(tmp / "repo")],
             ["make", "bootstrap"], ["make", "up", "PROFILES=core"], ["make", "test"]]
    log = []
    try:
        for i, cmd in enumerate(steps):
            t0 = time.monotonic()
            r = subprocess.run(cmd, cwd=tmp if i == 0 else tmp / "repo", env=env, capture_output=True, text=True,
                               timeout=1800)
            log.append(f"{' '.join(cmd[:3]) if i == 0 else ' '.join(cmd)} {time.monotonic() - t0:.1f}s")
            if r.returncode != 0:
                tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
                return Check("R2", False, f"{'; '.join(log)} FAILED: {' | '.join(tail)[:300]}",
                             "Fresh clone deploys by following the documented commands")
        return Check("R2", True, "; ".join(log), "Fresh clone deploys by following the documented commands")
    finally:
        if (tmp / "repo/infra/compose/docker-compose.yml").exists() and (tmp / "repo/.env").exists():
            subprocess.run(["docker", "compose", "-f", "infra/compose/docker-compose.yml", "--env-file", ".env",
                            "--profile", "core", "down", "-v"], cwd=tmp / "repo", env=env, capture_output=True)
        shutil.rmtree(tmp, ignore_errors=True)


def band(ratio: float) -> str:
    return ("Above standards" if ratio >= 1.0 else "Meets standards" if ratio >= 0.75 else
            "Approaching standards" if ratio >= 0.5 else "Below standards")


def report(checks: list[Check], deploy: bool, scope: str = "") -> str:
    lines = ([scope, ""] if scope else []) + ["| criterion | pts | checks passed | band (estimate) |", "|---|---|---|---|"]
    for key, (name, pts) in CRITERIA.items():
        mine = [c for c in checks if c.id.startswith(key)]
        ok = sum(c.ok for c in mine)
        note = "" if key != "R" or deploy else " (R2 deploy not run: add DEPLOY=1)"
        verdict = "not assessed (run with DEPLOY=1)" if key == "R" and not deploy else (
            band(ok / len(mine)) if mine else "n/a")
        lines.append(f"| {name} | {pts} | {ok}/{len(mine)}{note} | {verdict} |")
    lines += ["", "| check | result | evidence |", "|---|---|---|"]
    lines += [f"| {c.id} {c.title} | {'PASS' if c.ok else 'FAIL'} | {c.evidence} |" for c in checks]
    lines += ["", "Bands are an estimate from the pass ratio of these checks, not a grade."]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="submission_check.py", description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--deploy", action="store_true", help="also clone + bootstrap + up core + test")
    ap.add_argument("--ref", help="branch to clone for --deploy (default: the remote's default branch)")
    a = ap.parse_args(argv)
    checks = run_checks(Path(a.root), deploy=a.deploy, ref=a.ref)
    scope = f"Static checks: {Path(a.root).resolve()}" + (f" · deploy: fresh clone of {a.ref or 'the default branch'}" if a.deploy else "")
    print(report(checks, a.deploy, scope))
    return 0 if all(c.ok for c in checks) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
