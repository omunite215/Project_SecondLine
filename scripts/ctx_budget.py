#!/usr/bin/env python3
"""Estimate the context this repo's Claude Code config adds (≈ chars/4).
ALWAYS = loaded every session. ON DEMAND = only when a matching file, skill or subagent is used.
Usage: python3 scripts/ctx_budget.py [--max TOKENS]   (exit 1 if ALWAYS exceeds --max). Stdlib only."""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def tok(s: str) -> int:
    return len(s) // 4


def nocomments(t: str) -> str:
    return re.sub(r"<!--.*?-->", "", t, flags=re.S)


def front(t: str) -> str:
    m = re.match(r"^---\n(.*?)\n---\n", t, re.S)
    return m.group(1) if m else ""


def desc(t: str) -> str:
    m = re.search(r"^description:\s*(.+)$", front(t), re.M)
    return m.group(1) if m else ""


always, ondemand = [], []
if (ROOT / "CLAUDE.md").exists():
    always.append(("CLAUDE.md", tok(nocomments((ROOT / "CLAUDE.md").read_text(encoding="utf-8")))))
local = ROOT / "CLAUDE.local.md"
examples = sorted(ROOT.glob("CLAUDE.local.md.*.example"))
src = local if local.exists() else (max(examples, key=lambda p: p.stat().st_size) if examples else None)
if src:
    always.append((src.name if src == local else f"{src.name} (largest example)", tok(nocomments(src.read_text(encoding="utf-8")))))
for r in sorted((ROOT / ".claude/rules").rglob("*.md")):
    t = r.read_text(encoding="utf-8")
    (ondemand if "paths:" in front(t) else always).append((str(r.relative_to(ROOT)), tok(t)))
for s in sorted((ROOT / ".claude/skills").glob("*/SKILL.md")):
    t = s.read_text(encoding="utf-8")
    if not re.search(r"^disable-model-invocation:\s*true", front(t), re.M):
        always.append((f"{s.relative_to(ROOT)} [description]", tok(desc(t))))
    ondemand.append((f"{s.relative_to(ROOT)} [when invoked]", tok(t)))
for a in sorted((ROOT / ".claude/agents").glob("*.md")):
    t = a.read_text(encoding="utf-8")
    always.append((f"{a.relative_to(ROOT)} [description]", tok(desc(t))))
    ondemand.append((f"{a.relative_to(ROOT)} [own context]", tok(t)))
try:
    out = subprocess.run([sys.executable, str(ROOT / "scripts/board.py"), "brief"], capture_output=True, text=True, timeout=20).stdout
    always.append(("SessionStart hook: [board] brief", tok(out)))
    always.append(("SessionStart hook: [skills] line (estimate)", 45))
except Exception:
    pass
for n in sorted(ROOT.glob("**/CLAUDE.md")):
    if n.parent != ROOT and "node_modules" not in n.parts:
        ondemand.append((str(n.relative_to(ROOT)), tok(nocomments(n.read_text(encoding="utf-8")))))

total = sum(t for _, t in always)
print("ALWAYS LOADED (every session)")
for name, t in always:
    print(f"  {t:>6}  {name}")
print(f"  {total:>6}  TOTAL (plus Claude Code's system prompt, tool definitions and enabled plugins — see /context)")
print("\nON DEMAND")
for name, t in ondemand:
    print(f"  {t:>6}  {name}")
limit = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else None
if limit and total > limit:
    print(f"\nOVER BUDGET: {total} > {limit}. Move detail into path-scoped rules, nested CLAUDE.md files or skills.", file=sys.stderr)
    sys.exit(1)
