#!/usr/bin/env python3
"""PreToolUse (Edit|Write) guard for hidden-truth isolation (REQ-006, T-DOM-03, CLAUDE.md rule 4).
Blocks edits that would wire Truth/grader access into runtime services or the console.
Exit 2 + stderr = blocked (Claude sees the reason). Exit 0 = no objection. Never breaks the session.
The CI leakage scan (KG-05) is the real gate; this hook gives early feedback."""
import json
import re
import sys

RUNTIME_DIRS = ("services/agent/", "services/mcp-adapter/", "services/gateway/", "services/ledger/",
                "services/supervisor/", "apps/console/")
PATTERNS = [
    (re.compile(r"\b(?:from|import)\s+sl_factory\.(?:truth|oracle)\b"), "imports the privileged truth module"),
    (re.compile(r"\b(?:from|import)\s+sl_eval\.(?:grader|scripted)\b"), "imports the grader"),
    (re.compile(r"data/generated/[^/\s'\"]+/truth"), "references a truth directory"),
    (re.compile(r"SLCANARY-[0-9A-Fa-f]{6,}"), "contains a truth canary token"),
]
TEST_PATH = re.compile(r"(/tests?/|/src/test/|_test\.|\.test\.|\.spec\.|Test\.java$)")


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    ti = data.get("tool_input") or {}
    path = "/" + str(ti.get("file_path") or "").replace("\\", "/").lstrip("/")
    text = "\n".join(str(ti.get(k) or "") for k in ("content", "new_string"))
    if not text or not any("/" + d in path for d in RUNTIME_DIRS) or TEST_PATH.search(path):
        return 0
    for rx, why in PATTERNS:
        if rx.search(text):
            print(f"Blocked by truth-isolation guard: {path.lstrip('/')} {why}. Runtime services and the console "
                  "must never access hidden truth (CLAUDE.md rule 4, .claude/rules/truth-isolation.md). "
                  "If this is a false positive, explain why and ask the human to make the edit manually.",
                  file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
