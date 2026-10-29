"""OM-27 submission rubric check (§23, T-DOC-01, NFR-11): each rubric criterion maps to executable checks.
Runs scripts/submission_check.py against throwaway trees: a clean tree passes, each defect fails its check.
Stdlib only, like the kit: python3 -m unittest discover -s tests/kit"""
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import submission_check as sc  # noqa: E402  # pyright: ignore[reportMissingImports]

CLAUDE_MD = """# x
## Repo map
```text
services/ledger/    Java ledger    Om
scripts/            tooling
```
"""
README = """# Demo
## Prerequisites
- Docker Engine with Compose 2.17+ · Java 21 (only to run Java tests on the host) · Python 3.12 · uv 0.13+
## Quickstart
```bash
make bootstrap
make up PROFILES="core"
make test
```
"""
MAKEFILE = """define todo
@echo TODO; exit 1
endef
bootstrap: ## once
\t@echo ok
up: ## start
\t@echo ok
test: ## tests
\t@echo ok
later: ## planned
\t$(call todo,XX-01)
"""


class Tree(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.put("CLAUDE.md", CLAUDE_MD)
        self.put("README.md", README)
        self.put("Makefile", MAKEFILE)
        self.put(".env.example", "# db\nPOSTGRES_PASSWORD=\n")
        self.put("infra/compose/docker-compose.yml", "services:\n  db:\n    environment:\n      P: ${POSTGRES_PASSWORD:?x}\n")
        self.put("services/ledger/README.md", "# ledger\n`make test`\n")
        self.put("services/ledger/src/Main.java", "// Ledger entry point.\nclass Main {}\n")
        self.put("services/ledger/src/test/MainTest.java", "class MainTest {}\n")
        self.put("scripts/tool.py", '"""Does a thing."""\n')

    def tearDown(self):
        shutil.rmtree(self.root)

    def put(self, rel: str, text: str):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(text) if text.startswith("\n") else text)

    def failing(self) -> dict[str, str]:
        return {c.id: c.evidence for c in sc.run_checks(self.root) if not c.ok}

    def assertFlags(self, check_id: str):
        self.assertIn(check_id, self.failing())


class Checks(Tree):
    def test_OM_27_clean_tree_fails_only_on_planned_targets(self):
        self.assertEqual(set(self.failing()), {"P1"})  # `later` is a stub target: placeholders count against completeness

    def test_OM_27_missing_repo_map_dir_flagged(self):
        shutil.rmtree(self.root / "services/ledger")
        self.assertFlags("O1")

    def test_OM_27_stray_root_file_flagged(self):
        self.put("notes.txt", "scratch\n")
        self.assertFlags("O2")

    def test_OM_27_component_without_readme_flagged(self):
        (self.root / "services/ledger/README.md").unlink()
        self.assertFlags("O3")

    def test_OM_27_readme_without_quickstart_flagged(self):
        self.put("README.md", "# Demo\nNothing here.\n")
        self.assertFlags("D1")
        self.assertFlags("D2")

    def test_OM_27_doc_ref_to_stub_or_missing_target_flagged(self):
        self.put("services/ledger/README.md", "# ledger\nRun `make later` then `make nope`.\n")
        evidence = self.failing()["D3"]
        self.assertIn("later", evidence)
        self.assertIn("nope", evidence)

    def test_OM_27_compose_var_missing_from_env_example_flagged(self):
        self.put(".env.example", "OTHER=\n")
        self.assertFlags("D4")

    def test_OM_27_script_without_docstring_flagged(self):
        self.put("scripts/bare.py", "x = 1\n")
        self.assertFlags("Q1")

    def test_OM_27_todo_without_task_id_flagged(self):
        self.put("services/ledger/src/Main.java", "// TO" "DO fix later\nclass Main {}\n")  # split literal: this file isn't scanned as one
        self.assertFlags("Q2")

    def test_OM_27_code_without_tests_flagged(self):
        shutil.rmtree(self.root / "services/ledger/src/test")
        self.assertFlags("Q3")

    def test_OM_27_component_with_docs_only_flagged(self):
        shutil.rmtree(self.root / "services/ledger/src")
        self.assertFlags("P2")

    def test_OM_27_doc_placeholder_flagged(self):
        self.put("README.md", README + "\nSubmission date: ______\n")
        self.assertFlags("P3")

    def test_OM_27_build_file_without_lock_flagged(self):
        self.put("pyproject.toml", "[project]\nname='x'\n")
        self.assertFlags("P4")

    def test_OM_27_unpinned_image_flagged(self):
        self.put("infra/compose/docker-compose.yml",
                 "services:\n  db:\n    image: postgres:latest\n    environment:\n      P: ${POSTGRES_PASSWORD:?x}\n")
        self.assertFlags("R1")


class NoFalsePositives(Tree):
    def test_OM_27_target_with_equals_in_help_is_found(self):
        self.put("Makefile", MAKEFILE + "skills-check: ## Verify: make skills-check [CARD=OM-06]\n\t@echo ok\nX := 1\n")
        self.assertIn("skills-check", sc.make_targets(self.root))
        self.assertNotIn("X", sc.make_targets(self.root))

    def test_OM_27_doc_command_family_matches_any_member(self):
        self.put("Makefile", MAKEFILE + "hpc-check: ## h\n\t@echo ok\n")
        self.put("services/ledger/README.md", "# ledger\nUse `make hpc-*` for the cluster.\n")
        self.assertNotIn("D3", self.failing())

    def test_OM_27_todo_word_in_a_string_is_not_a_todo_comment(self):
        self.put("scripts/tool.py", '"""Does a thing."""\nmsg = "(TO' 'DO stub)"\n')
        self.assertNotIn("Q2", self.failing())
        self.put("scripts/tool.py", '"""Does a thing."""\nx = 1  # TO' 'DO later\n')
        self.assertIn("Q2", self.failing())


class Report(unittest.TestCase):
    def test_OM_27_band_thresholds(self):
        self.assertEqual([sc.band(r) for r in (1.0, 0.8, 0.6, 0.2)],
                         ["Above standards", "Meets standards", "Approaching standards", "Below standards"])

    def test_OM_27_deployment_not_banded_without_live_run(self):
        # Pinning alone can't earn a deployment band; only the fresh-clone run (R2) can.
        out = sc.report([sc.Check("R1", True, "pinned", "pins")], deploy=False)
        row = next(l for l in out.splitlines() if l.startswith("| Deployment"))
        self.assertIn("not assessed", row)
        self.assertNotIn("Above standards", row)

    def test_OM_27_cli_exit_code_and_table(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            (tmp / "README.md").write_text("# x\n")
            r = subprocess.run([sys.executable, str(ROOT / "scripts/submission_check.py"), "--root", str(tmp)],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)
            for criterion in ("Code organization", "Technical documentation", "Code quality", "Completeness",
                              "Deployment and reproducibility"):
                self.assertIn(criterion, r.stdout)
            self.assertIn("estimate", r.stdout.lower())
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
