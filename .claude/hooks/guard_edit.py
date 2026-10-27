#!/usr/bin/env python3
"""PreToolUse (Edit|Write|MultiEdit|NotebookEdit) guard for hidden-truth isolation (REQ-006, T-DOM-03, CLAUDE.md rule 4).
Blocks edits that would wire Truth/grader access into runtime services or the console.
Exit 2 + stderr = blocked (Claude sees the reason). Exit 0 = no objection. Never breaks the session.
The CI leakage scan (KG-05) is the real gate; this hook gives early feedback."""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

RUNTIME_DIRS = ("services/agent/", "services/mcp-adapter/", "services/gateway/", "services/ledger/",
                "services/supervisor/", "apps/console/")
PATTERNS = [
    (re.compile(r"\bsl_factory\s*\.\s*(?:truth|oracle)\b"
                r"|\bfrom\s+sl_factory\s+import\s*(?:\([\w\s,]*|[\w \t,]*)\b(?:truth|oracle)\b"),
     "references the privileged truth module"),
    (re.compile(r"\bsl_eval\s*\.\s*(?:grader|scripted)\b"
                r"|\bfrom\s+sl_eval\s+import\s*(?:\([\w\s,]*|[\w \t,]*)\b(?:grader|scripted)\b"),
     "references the grader"),
    (re.compile(r"data/generated/[^/\s'\"]+/truth"), "references a truth directory"),
    (re.compile(r"SLCANARY-[0-9A-Fa-f]{6,}"), "contains a truth canary token"),
]
# Only a service's own test tree is exempt; matched on the normalised repo-relative path.
TEST_DIRS = re.compile(r"^(services/[^/]+/(tests?|src/test)|apps/console/(tests|e2e))/")
NEW_TEXT = ("content", "new_string", "new_source")  # Write, Edit, NotebookEdit
KNOWN = {*NEW_TEXT, "edits", "file_path", "notebook_path", "old_string", "replace_all", "cell_id", "cell_type", "edit_mode"}


def new_text(ti: dict) -> tuple[str, set[str]]:
    """Text an edit would write (Write, Edit, MultiEdit, NotebookEdit) + any fields the guard doesn't know."""
    parts = [str(ti.get(k) or "") for k in NEW_TEXT]
    unknown = set(ti) - KNOWN
    for e in ti.get("edits") or []:
        if not isinstance(e, dict):
            unknown.add("edits[]")
            continue
        parts.append(str(e.get("new_string") or ""))
        unknown |= {f"edits[].{k}" for k in set(e) - {"old_string", "new_string", "replace_all"}}
    return "\n".join(parts), unknown


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    ti = data.get("tool_input") or {}
    p = Path(str(ti.get("file_path") or ti.get("notebook_path") or "").replace("\\", "/"))
    if not p.is_absolute():
        p = Path(data.get("cwd") or os.getcwd()) / p
    try:
        path = p.resolve().relative_to(ROOT).as_posix()  # collapses .., //, ./ and symlinks
    except ValueError:
        return 0  # outside this repository
    if not path.startswith(RUNTIME_DIRS) or TEST_DIRS.match(path):
        return 0
    text, unknown = new_text(ti)
    if unknown:
        print(f"Blocked by truth-isolation guard: unrecognised edit fields {sorted(unknown)} for {path}; "
              "the guard can't inspect them. Use Edit or Write, or ask the human to make the edit.", file=sys.stderr)
        return 2
    for rx, why in PATTERNS:
        if rx.search(text):
            print(f"Blocked by truth-isolation guard: {path} {why}. Runtime services and the console "
                  "must never access hidden truth (CLAUDE.md rule 4, .claude/rules/truth-isolation.md). "
                  "If this is a false positive, explain why and ask the human to make the edit manually.",
                  file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
