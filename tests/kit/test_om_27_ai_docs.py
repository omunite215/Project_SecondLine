"""OM-27 AI-docs move: root CLAUDE.md is an @import stub; the always-loaded budget must still count the imported
file (Claude Code loads it every session). Stdlib only."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class CtxBudgetFollowsImports(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(ROOT / "scripts", self.tmp / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "docs/team", self.tmp / "docs/team")
        (self.tmp / ".claude/rules").mkdir(parents=True)
        (self.tmp / "docs/ai").mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def budget(self) -> str:
        return subprocess.run([sys.executable, str(self.tmp / "scripts/ctx_budget.py")], capture_output=True,
                              text=True, cwd=self.tmp).stdout

    def test_OM_27_imported_claude_md_counts_as_always_loaded(self):
        (self.tmp / "CLAUDE.md").write_text("@docs/ai/CLAUDE.md\n")
        (self.tmp / "docs/ai/CLAUDE.md").write_text("word " * 400)
        out = self.budget()
        self.assertIn("ON DEMAND", out)  # the real section header; split on it, not a guess
        always = out.split("ON DEMAND")[0]
        self.assertIn("docs/ai/CLAUDE.md", always)

    def test_OM_27_root_stub_is_only_an_import(self):
        lines = [l for l in (ROOT / "CLAUDE.md").read_text().splitlines() if l.strip() and not l.startswith("<!--")]
        self.assertEqual(lines, ["@docs/ai/CLAUDE.md"])

    def test_OM_27_ai_files_live_in_docs_ai(self):
        for f in ("docs/ai/CLAUDE.md", "docs/ai/README.md", "docs/ai/CLAUDE.local.md.om.example",
                  "docs/ai/CLAUDE.local.md.kunal.example"):
            self.assertTrue((ROOT / f).exists(), f)
        for f in ("START_HERE.md", "CLAUDE.local.md.om.example", "CLAUDE.local.md.kunal.example"):
            self.assertFalse((ROOT / f).exists(), f)


if __name__ == "__main__":
    unittest.main()
