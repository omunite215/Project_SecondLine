"""OM-04 (found in OM-05): libs/contracts-java copies packages/contracts onto the classpath at build time, so every
service image that depends on it must copy packages/contracts into its build stage — or the jar ships without
schemas and the ledger fails at startup (TruthKeys) / validation fails closed. Stdlib only."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class DockerContracts(unittest.TestCase):
    def test_OM_04_images_using_contracts_copy_them(self):
        checked = 0
        for build in sorted(ROOT.glob("services/*/build.gradle.kts")):
            if 'project(":libs:contracts-java")' not in build.read_text():
                continue
            dockerfile = build.parent / "Dockerfile"
            stage = dockerfile.read_text().split("\nFROM ")[1]  # [0] is the header comment; [1] the build stage
            self.assertRegex(stage, r"(?m)^COPY packages/contracts packages/contracts$", dockerfile)
            checked += 1
        self.assertGreaterEqual(checked, 1)

    def test_OM_04_dockerignore_keeps_contracts(self):
        lines = (ROOT / ".dockerignore").read_text().split()
        self.assertFalse(any(re.match(r"^/?packages(/contracts)?/?$", l) for l in lines))


if __name__ == "__main__":
    unittest.main()
