"""OM-01 Gradle build hygiene (§7 §19): pinned, checksum-verified wrapper; memory caps for a 16 GB laptop.
Stdlib only, like the kit: python3 -m unittest discover -s tests/kit"""
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def props(path: Path) -> dict[str, str]:
    return dict(l.split("=", 1) for l in path.read_text().splitlines() if "=" in l and not l.startswith("#"))


class Gradle(unittest.TestCase):
    def test_OM_01_wrapper_pinned(self):
        p = props(ROOT / "gradle/wrapper/gradle-wrapper.properties")
        self.assertIn("gradle-8.14.6-bin.zip", p["distributionUrl"])
        self.assertRegex(p.get("distributionSha256Sum", ""), r"^[0-9a-f]{64}$")

    def test_OM_01_gradle_memory_limits(self):
        p = props(ROOT / "gradle.properties")
        self.assertIn("-Xmx512m", p["org.gradle.jvmargs"])
        self.assertEqual(p["org.gradle.workers.max"], "4")

    def test_OM_01_subprojects_declared(self):
        s = (ROOT / "settings.gradle.kts").read_text()
        for proj in ("services:ledger", "services:gateway", "libs:contracts-java"):
            self.assertIn(f'"{proj}"', s)

    def test_OM_01_spring_boot_pinned(self):
        cat = (ROOT / "gradle/libs.versions.toml").read_text()
        self.assertRegex(cat, r'(?m)^spring-boot\s*=\s*"3\.5\.16"$')

    def test_OM_01_executables_committed_executable(self):
        # CI and Docker builds use the git index mode, not the local file mode.
        for f in ("gradlew", "infra/db/init/01-logins.sh"):
            mode = subprocess.run(["git", "ls-files", "-s", f], cwd=ROOT, capture_output=True, text=True).stdout[:6]
            self.assertEqual(mode, "100755", f)

    def test_OM_01_wrapper_scripts_lf(self):
        self.assertNotIn(b"\r\n", (ROOT / "gradlew").read_bytes())


if __name__ == "__main__":
    unittest.main()
