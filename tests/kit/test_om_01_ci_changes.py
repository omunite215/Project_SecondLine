"""OM-01 CI change detection (§19): which jobs a PR's diff needs. Fails closed: unknown diff runs everything.
Stdlib only, like the kit: python3 -m unittest discover -s tests/kit"""
import shutil
import subprocess
import sys
import tempfile
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

    def test_OM_01_stack_covers_everything_its_images_and_configs_use(self):
        # The stack job builds the Java images and mounts infra configs: any of these can break `make up`.
        for p in ("infra/observability/otel-collector.yaml", "infra/toxiproxy/toxiproxy.json",
                  "services/ledger/src/main/resources/application.yml", "services/gateway/build.gradle.kts",
                  "build.gradle.kts", "settings.gradle.kts", "gradle/libs.versions.toml", "gradle.properties"):
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


class ChangedInTempRepo(unittest.TestCase):
    """changed() against a throwaway repo: odd filenames and renames must not hide a path."""

    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.invalid")
        self.git("config", "user.name", "t")
        (self.repo / "infra/db").mkdir(parents=True)
        (self.repo / "infra/db/init.sql").write_text("select 1;\n")
        self.commit("base")
        self.base = self.git("rev-parse", "HEAD").strip()

    def tearDown(self):
        shutil.rmtree(self.repo)

    def git(self, *args: str) -> str:
        return subprocess.run(["git", *args], cwd=self.repo, capture_output=True, text=True, check=True).stdout

    def commit(self, msg: str):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", msg)

    def test_OM_01_rename_out_of_infra_still_runs_stack(self):
        (self.repo / "docs").mkdir()
        self.git("mv", "infra/db/init.sql", "docs/init.sql")
        self.commit("move")
        paths = ci_changes.changed(self.base, "HEAD", cwd=self.repo)
        self.assertIn("infra/db/init.sql", paths)
        self.assertTrue(ci_changes.classify(paths)["stack"])

    def test_OM_01_odd_filenames_are_exact(self):
        for name in ("infra/db/a b.sql", "infra/db/caf\u00e9.sql"):
            (self.repo / name).write_text("x\n")
        self.commit("odd")
        self.assertEqual(sorted(ci_changes.changed(self.base, "HEAD", cwd=self.repo)),
                         ["infra/db/a b.sql", "infra/db/caf\u00e9.sql"])

    def test_OM_01_option_like_ref_runs_all(self):
        out = self.repo / "pwned"
        self.assertEqual(ci_changes.changed(f"--output={out}", "HEAD", cwd=self.repo), [])
        self.assertEqual(list(self.repo.glob("pwned*")), [], "ref was parsed as a git option")


if __name__ == "__main__":
    unittest.main()
