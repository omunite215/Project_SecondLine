"""OM-26 kit integrity (§19 §21): board checks, skills gate sources, permission layer, CI parity.
Stdlib only, like the kit: python3 -m unittest discover -s tests/kit"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import skills  # noqa: E402  # pyright: ignore[reportMissingImports]


class BoardInTempCopy(unittest.TestCase):
    """board.py run against a throwaway copy of scripts/ + docs/team/, never the real boards."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(ROOT / "scripts", self.tmp / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "docs/team", self.tmp / "docs/team")
        self.team = self.tmp / "docs/team"

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def board(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(self.tmp / "scripts/board.py"), *args],
                              capture_output=True, text=True, cwd=self.tmp)

    def test_OM_26_board_copy_is_valid(self):
        self.assertEqual(self.board("check").returncode, 0)

    def test_OM_26_cut_cards_do_not_cover_spec_ids(self):
        for f in ("OM.md", "KUNAL.md", "SHARED.md"):
            p = self.team / f
            p.write_text(re.sub(r"status:\s*\w+", "status: cut", p.read_text()))
        r = self.board("check")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("uncovered", r.stdout)

    def test_OM_26_summary_write_fails_without_markers(self):
        p = self.team / "PLAN.md"
        p.write_text(p.read_text().replace("<!-- BEGIN:summary -->", "<!-- BEGIN:summry -->"))
        self.assertNotEqual(self.board("summary", "--write").returncode, 0)

    def test_OM_26_set_fails_when_meta_has_no_status(self):
        p = self.team / "OM.md"
        p.write_text(p.read_text().replace("- meta: P1 | M-0 | 0.5d | deps: SH-01 | status: todo",
                                           "- meta: P1 | M-0 | 0.5d | deps: SH-01"))
        r = self.board("set", "OM-26", "review", "--evidence", "x")
        self.assertNotEqual(r.returncode, 0, r.stdout)


class SkillsGateSources(unittest.TestCase):
    P = {"name": "superpowers", "marketplace": "claude-plugins-official"}

    def test_OM_26_plugin_from_other_marketplace_is_not_accepted(self):
        self.assertIsNone(skills.plugin_state({"superpowers@evil-mkt": True}, self.P))

    def test_OM_26_plugin_listed_without_marketplace_still_matches(self):
        self.assertTrue(skills.plugin_state({"superpowers": True}, self.P))
        self.assertTrue(skills.plugin_state({"superpowers@claude-plugins-official": True}, self.P))

    def test_OM_26_vendored_skill_must_be_pinned(self):
        self.assertIn("not pinned", skills.lock_problem("langgraph-fundamentals", "abc123", {}) or "")
        self.assertIn("not at the locked commit",
                      skills.lock_problem("langgraph-fundamentals", "abc123", {"langgraph-fundamentals": {"commit": "def456"}}) or "")
        self.assertIsNone(skills.lock_problem("langgraph-fundamentals", "abc123",
                                              {"langgraph-fundamentals": {"commit": "abc123"}}))

    def test_OM_26_corrupt_lock_is_not_swallowed(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d, "skills.lock.json")
            bad.write_text("{not json")
            with mock.patch.object(skills, "LOCK", bad):
                with self.assertRaises(ValueError):
                    skills.load_lock()
            with mock.patch.object(skills, "LOCK", Path(d, "missing.json")):
                self.assertEqual(skills.load_lock(), {})


class PermissionLayer(unittest.TestCase):
    def test_OM_26_skill_installs_need_human_approval(self):
        perms = json.loads((ROOT / ".claude/settings.json").read_text())["permissions"]
        self.assertNotIn("Bash(python3 scripts/*)", perms["allow"])
        self.assertFalse([r for r in perms["allow"] if "skills.py" in r and "install" in r or r.endswith("skills.py *)")])
        self.assertIn("Bash(python3 scripts/skills.py install *)", perms["ask"])

    def test_OM_26_project_skills_only_preapprove_the_gate(self):
        for f in sorted((ROOT / ".claude/skills").glob("*/SKILL.md")):
            for line in f.read_text().splitlines():
                if "skills.py" in line and line.strip().startswith("- 'Bash("):
                    self.assertIn('skills.py" gate *', line, f"{f.parent.name}: {line.strip()}")


class CiParity(unittest.TestCase):
    def test_OM_26_kit_check_includes_generated_docs_check(self):
        mk = (ROOT / "Makefile").read_text()
        m = re.search(r"^kit-check:([^#\n]*)", mk, re.M)
        assert m
        deps = m.group(1).split()
        self.assertIn("trace-check", deps)
        self.assertRegex(mk, r"(?m)^trace-check:")

    def test_OM_26_claude_review_runs_the_trusted_workflow(self):
        """Required reviewers on environments need Enterprise for private repos, so the gate is
        pull_request_target: workflow + label check come from protected main, never from the PR."""
        wf = (ROOT / ".github/workflows/claude-review.yml").read_text()
        self.assertRegex(wf, r"(?m)^  pull_request_target:\n    types: \[labeled\]$")
        self.assertNotRegex(wf, r"(?m)^  pull_request:")
        self.assertNotIn("environment:", wf)
        self.assertNotRegex(wf, r"(?m)^\s+ref:", "never check out the PR head before the action (secrets are in scope)")
        self.assertIn("github.event.pull_request.head.repo.full_name == github.repository", wf)


if __name__ == "__main__":
    unittest.main()
