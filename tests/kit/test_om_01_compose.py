"""OM-01 compose hygiene (§7, infra/CLAUDE.md): every service healthchecked, memory-capped, pinned, profiled,
loopback-only, secrets from .env only. Reads `docker compose config`; needs docker (fails, not skips, in CI)."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = ROOT / "infra/compose/docker-compose.yml"
PROFILES = ("core", "app", "events", "obs", "ui", "chaos")
MB = 1024 * 1024


def load_config() -> dict:
    tmp = Path(tempfile.mkdtemp())
    try:
        env = tmp / ".env"
        subprocess.run([sys.executable, str(ROOT / "scripts/bootstrap_env.py"), "--path", str(env)], check=True,
                       capture_output=True)
        cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), "--env-file", str(env)]
        for p in PROFILES:
            cmd += ["--profile", p]
        r = subprocess.run(cmd + ["config", "--format", "json"], capture_output=True, text=True, cwd=ROOT)
        if r.returncode != 0:
            raise AssertionError(f"docker compose config failed: {r.stderr[:300]}")
        return json.loads(r.stdout)
    finally:
        shutil.rmtree(tmp)


@unittest.skipUnless(shutil.which("docker") or os.environ.get("CI"), "docker not installed")
class Compose(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.services = load_config()["services"]

    def one_shots(self) -> set[str]:
        """Jobs that run to completion (e.g. ledger-migrate, ADR-019): another service gates on their exit."""
        return {dep for s in self.services.values() for dep, cond in s.get("depends_on", {}).items()
                if cond.get("condition") == "service_completed_successfully"}

    def test_OM_01_every_service_healthchecked(self):
        for name, s in self.services.items():
            if name in self.one_shots():
                continue
            self.assertTrue(s.get("healthcheck", {}).get("test"), name)

    def test_OM_03_one_shot_jobs_never_restart(self):
        # Exempt from healthchecks only because they exit; a restarting "one-shot" would be a daemon.
        shots = self.one_shots()
        self.assertIn("ledger-migrate", shots)
        for name in shots:
            self.assertEqual(self.services[name].get("restart", "no"), "no", name)

    def test_OM_01_every_service_mem_limited(self):
        for name, s in self.services.items():
            self.assertGreater(int(s.get("mem_limit", 0)), 0, name)
        core = sum(int(s["mem_limit"]) for s in self.services.values() if "core" in s["profiles"])
        self.assertLessEqual(core, 768 * MB)

    def test_OM_01_images_pinned(self):
        for name, s in self.services.items():
            if "build" in s:
                continue
            tag = s["image"].rsplit(":", 1)[-1] if ":" in s["image"].split("/")[-1] else ""
            self.assertRegex(tag, r"\d", f"{name}: {s['image']} is not pinned")
            self.assertNotIn("latest", tag, name)

    def test_OM_01_profiles_known(self):
        for name, s in self.services.items():
            self.assertTrue(s.get("profiles"), name)
            self.assertLessEqual(set(s["profiles"]), set(PROFILES), name)
        self.assertTrue({"core", "app", "events", "obs", "chaos"} <=
                        {p for s in self.services.values() for p in s["profiles"]})

    def test_OM_01_ports_loopback_only(self):
        for name, s in self.services.items():
            for port in s.get("ports", []):
                self.assertEqual(port.get("host_ip"), "127.0.0.1", f"{name}: {port}")

    def test_OM_01_no_literal_secrets(self):
        for line in COMPOSE_FILE.read_text().splitlines():
            m = re.match(r"\s*([A-Z0-9_]*(PASSWORD|SECRET|TOKEN|KEY)[A-Z0-9_]*):\s*(.+)$", line)
            if m:
                self.assertRegex(m.group(3).strip(), r"^\$\{[A-Z0-9_]+:\?", line)

    def test_OM_01_built_images_never_pulled(self):
        # secondline/* images exist only locally; pulling them first fails (and could fetch a squatted image).
        for name, s in self.services.items():
            if "build" in s:
                self.assertEqual(s.get("pull_policy"), "build", name)

    def test_OM_01_postgres_healthy_only_after_init(self):
        # Unix-socket pg_isready answers during the entrypoint's init server; TCP only once init is done.
        self.assertIn("-h 127.0.0.1", " ".join(self.services["postgres"]["healthcheck"]["test"]))

    def test_OM_01_jvm_heap_capped(self):
        for name in ("ledger", "gateway"):
            self.assertIn("-Xmx512m", self.services[name]["environment"]["JAVA_TOOL_OPTIONS"])
            self.assertLessEqual(int(self.services[name]["mem_limit"]), 768 * MB)


class Dockerfiles(unittest.TestCase):
    def test_OM_01_dockerfiles_non_root(self):
        for svc in ("ledger", "gateway"):
            text = (ROOT / f"services/{svc}/Dockerfile").read_text()
            runtime = text.split("\nFROM ")[-1]
            self.assertRegex(runtime, r"(?m)^USER (?!root)\S+", svc)
            self.assertIn("eclipse-temurin:21.0.12.1_1-jre-noble", runtime, svc)
            self.assertNotIn(":latest", text, svc)

    def test_OM_01_dockerignore_excludes_secrets_and_builds(self):
        lines = (ROOT / ".dockerignore").read_text().split()
        for pattern in (".env", ".git", "**/build", ".gradle", "data/attacks", "secrets"):  # eval packs are deny-listed
            self.assertIn(pattern, lines)


class InitScripts(unittest.TestCase):
    def test_OM_01_passwords_never_in_argv_or_error_log(self):
        text = (ROOT / "infra/db/init/01-logins.sh").read_text()
        psql_line = next(l for l in text.splitlines() if l.lstrip().startswith("psql"))
        self.assertNotIn("PASSWORD", psql_line)
        self.assertNotRegex(text, r"-v\s+\w+=\S*\$")
        self.assertIn("log_min_error_statement", text)


if __name__ == "__main__":
    unittest.main()
