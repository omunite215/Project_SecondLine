"""OM-01 docs (§21 DoD, T-DOC-01): the commands CLAUDE.md files advertise exist and aren't TODO stubs.
Stdlib only, like the kit: python3 -m unittest discover -s tests/kit"""
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OM01_TARGETS = ("bootstrap", "up", "down", "ps", "logs", "db-shell", "lint", "test")


def dry_run(target: str) -> str:
    return subprocess.run(["make", "-n", "--no-print-directory", target], cwd=ROOT, capture_output=True,
                          text=True).stdout


class Docs(unittest.TestCase):
    def test_OM_01_no_todo_for_om01(self):
        for t in OM01_TARGETS:
            self.assertNotIn("TODO(", dry_run(t), t)

    def test_OM_01_db_shell_follows_env_database(self):
        self.assertIn("POSTGRES_DB", dry_run("db-shell"))
        self.assertNotIn("-d secondline", dry_run("db-shell"))

    def test_OM_01_infra_claude_lists_real_commands(self):
        text = (ROOT / "infra/CLAUDE.md").read_text()
        targets = set(re.findall(r"`make ([a-z][\w-]*)", text))
        self.assertTrue({"bootstrap", "up", "down", "ps", "logs", "db-shell", "lint"} <= targets, targets)
        for t in targets:
            self.assertNotIn("TODO(", dry_run(t), f"infra/CLAUDE.md advertises stub `make {t}`")

    def test_OM_01_infra_claude_names_the_memory_budget(self):
        text = (ROOT / "infra/CLAUDE.md").read_text()
        for needle in ("768", "-Xmx512m", "free -g", "tests/infra"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
