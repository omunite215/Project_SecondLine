#!/usr/bin/env python3
"""Safe, bounded context snippets for skill injection. Never fails (a failed injected command would abort the skill).
  git | gh-auth | pr [N] | standup | ls <dir> | hpc"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sh(cmd: list[str], limit: int = 40) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=45, cwd=ROOT)
        lines = ((r.stdout or "") + (r.stderr if r.returncode else "")).strip().splitlines()
    except Exception as e:
        lines = [f"({cmd[0]} unavailable: {type(e).__name__})"]
    more = f"\n… ({len(lines) - limit} more lines)" if len(lines) > limit else ""
    return "\n".join(lines[:limit]) + more


def main(a: list[str]) -> int:
    what = a[0] if a else "git"
    if what == "git":
        print("branch: " + (sh(["git", "branch", "--show-current"], 1) or "(detached)"))
        print("status:\n" + (sh(["git", "status", "--short"]) or "(clean)"))
        print("diffstat vs HEAD:\n" + (sh(["git", "diff", "--stat", "HEAD"], 25) or "(none)"))
        print("commits not on origin/main:\n" + (sh(["git", "log", "--oneline", "origin/main..HEAD"], 20) or "(none)"))
    elif what == "gh-auth":
        print(sh(["gh", "auth", "status"], 4))
    elif what == "pr":
        n = a[1:2]
        print(sh(["gh", "pr", "view", *n], 60))
        print("checks:\n" + sh(["gh", "pr", "checks", *n], 30))
        print("files:\n" + sh(["gh", "pr", "diff", *n, "--name-only"], 80))
    elif what == "standup":
        print(sh(["git", "log", "--since=36 hours ago", "--no-merges", "--pretty=%an | %s"], 40) or "(no commits)")
    elif what == "ls":
        d = ROOT / (a[1] if len(a) > 1 else ".")
        print("\n".join(sorted(p.name for p in d.iterdir())) if d.is_dir() else f"({d.relative_to(ROOT)} does not exist yet)")
    elif what == "hpc":
        print(sh(["bash", str(ROOT / "scripts/hpc.sh"), "check"], 6))
    return 0


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except BrokenPipeError:
        pass
    sys.exit(0)
