"""OM-01 CI change detection (§19): which jobs a PR's diff needs. Fails closed: unknown diff runs everything.
Stdlib only, like the kit: python3 -m unittest discover -s tests/kit"""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import ci_changes  # noqa: E402  # pyright: ignore[reportMissingImports]

ALL = {"lint": True, "java": True, "stack": True}


class Classify(unittest.TestCase):
    def test_OM_01_java_paths(self):
        for p in ("services/ledger/src/main/java/X.java", "services/gateway/build.gradle.kts",
                  "libs/contracts-java/build.gradle.kts", "settings.gradle.kts", "gradle/libs.versions.toml",
                  "gradlew", "packages/contracts/errors.json"):
            self.assertTrue(ci_changes.classify([p])["java"], p)
        self.assertFalse(ci_changes.classify(["services/agent/main.py"])["java"])

    def test_OM_01_stack_paths(self):
        for p in ("infra/compose/docker-compose.yml", "infra/db/init/00-roles.sql", "services/ledger/Dockerfile",
                  ".env.example", "Makefile"):
            self.assertTrue(ci_changes.classify([p])["stack"], p)

    def test_OM_01_docs_only_runs_nothing_but_lint(self):
        self.assertEqual(ci_changes.classify(["docs/x.md", "README.md"]),
                         {"lint": True, "java": False, "stack": False})

    def test_OM_01_workflow_change_runs_all(self):
        self.assertEqual(ci_changes.classify([".github/workflows/ci.yml"]), ALL)

    def test_OM_01_empty_diff_runs_all(self):
        self.assertEqual(ci_changes.classify([]), ALL)


class Cli(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(ROOT / "scripts/ci_changes.py"), *args],
                              capture_output=True, text=True, cwd=ROOT)

    def test_OM_01_git_failure_runs_all(self):
        r = self.run_cli("--base", "0" * 40, "--head", "HEAD")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(set(r.stdout.split()), {"lint=true", "java=true", "stack=true"})

    def test_OM_01_real_diff(self):
        r = self.run_cli("--base", "HEAD", "--head", "HEAD")  # no changes → fail closed: run all
        self.assertEqual(set(r.stdout.split()), {"lint=true", "java=true", "stack=true"})


if __name__ == "__main__":
    unittest.main()
