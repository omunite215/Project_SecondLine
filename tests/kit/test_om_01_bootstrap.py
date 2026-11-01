"""OM-01 bootstrap (§7 NFR-11): a fresh clone gets a local .env with random secrets; nothing defaults.
Stdlib only, like the kit: python3 -m unittest discover -s tests/kit"""
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEYS = ("POSTGRES_PASSWORD", "LEDGER_SVC_PASSWORD", "LEDGER_MIGRATOR_PASSWORD", "GRADER_SVC_PASSWORD", "OPERATOR_SVC_PASSWORD",
        "GRAFANA_ADMIN_PASSWORD")


def env_file(path: Path) -> dict[str, str]:
    return dict(l.split("=", 1) for l in path.read_text().splitlines() if "=" in l and not l.startswith("#"))


class BootstrapEnv(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_bootstrap(self, path: Path) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(ROOT / "scripts/bootstrap_env.py"), "--path", str(path)],
                              capture_output=True, text=True)

    def test_OM_01_bootstrap_env_creates_secrets(self):
        p = self.tmp / ".env"
        self.assertEqual(self.run_bootstrap(p).returncode, 0)
        env = env_file(p)
        secrets = [env[k] for k in KEYS]
        self.assertTrue(all(len(s) >= 24 for s in secrets), secrets)
        self.assertEqual(len(set(secrets)), len(KEYS))
        self.assertEqual(env["POSTGRES_DB"], "secondline")
        self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600)

    def test_OM_01_bootstrap_env_never_overwrites(self):
        p = self.tmp / ".env"
        p.write_text("POSTGRES_PASSWORD=mine\n")
        self.assertEqual(self.run_bootstrap(p).returncode, 0)
        self.assertTrue(p.read_text().startswith("POSTGRES_PASSWORD=mine\n"))
        self.assertEqual(env_file(p)["POSTGRES_PASSWORD"], "mine")

    def test_OM_03_bootstrap_appends_missing_secret_keys(self):
        # A key added later (LEDGER_MIGRATOR_PASSWORD, ADR-019) reaches an existing .env without a reset.
        p = self.tmp / ".env"
        p.write_text("POSTGRES_PASSWORD=mine\n")
        os.chmod(p, 0o600)
        r = self.run_bootstrap(p)
        self.assertEqual(r.returncode, 0)
        env = env_file(p)
        self.assertEqual(env["POSTGRES_PASSWORD"], "mine")
        for k in KEYS:
            self.assertGreaterEqual(len(env[k]), 4, k)
        self.assertGreaterEqual(len(env["LEDGER_MIGRATOR_PASSWORD"]), 24)
        self.assertNotIn(env["LEDGER_MIGRATOR_PASSWORD"], r.stdout + r.stderr)  # never printed
        self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600)
        before = p.read_text()
        self.run_bootstrap(p)
        self.assertEqual(p.read_text(), before)  # second run: nothing missing, nothing changes

    def test_OM_01_env_example_has_no_values(self):
        env = env_file(ROOT / ".env.example")
        for k in KEYS:
            self.assertEqual(env[k], "", k)

    def test_OM_01_env_is_gitignored(self):
        r = subprocess.run(["git", "check-ignore", ".env"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)

    def test_OM_01_up_without_env_fails_clearly(self):
        r = subprocess.run(["make", "--no-print-directory", "up", f"ENV_FILE={self.tmp}/missing.env"], cwd=ROOT,
                           capture_output=True, text=True, env=dict(os.environ, PATH=os.environ["PATH"]))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("make bootstrap", r.stdout + r.stderr)


class Hook(unittest.TestCase):
    def test_OM_01_hook_tolerates_branches_without_config(self):
        # The hook lives in .git/ and outlives branch switches; a branch cut before the config existed
        # must still commit (found when SH-03 branched from main before OM-01 merged).
        mk = (ROOT / "Makefile").read_text()
        install = [l for l in mk.splitlines() if "pre-commit install" in l]
        self.assertTrue(install)
        for l in install:
            self.assertIn("--allow-missing-config", l)


if __name__ == "__main__":
    unittest.main()
