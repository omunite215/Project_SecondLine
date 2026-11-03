"""OM-05 G4 G5 (§11, OM-15): the gateway's signing key and operator token come from `make bootstrap`, never from git
or a printed value; compose hands them to the gateway read-only. Stdlib + the JDK (KeyGen runs as a single-file
source program, so the same generator works on both laptops)."""
import base64
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEYGEN = ROOT / "services/gateway/src/main/java/com/secondline/gateway/token/KeyGen.java"
COMPOSE = ROOT / "infra/compose/docker-compose.yml"


def gateway_block() -> str:
    m = re.search(r"(?ms)^  gateway:\n(.*?)(?=^  \S|\Z)", COMPOSE.read_text())
    assert m
    return m.group(1)


@unittest.skipUnless(shutil.which("java") or os.environ.get("CI"), "no JDK")  # CI: fail, never skip
class KeyGen(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def gen(self, path: Path) -> subprocess.CompletedProcess:
        return subprocess.run(["java", str(KEYGEN), str(path)], capture_output=True, text=True, timeout=120)

    def test_OM_05_keygen_writes_an_ed25519_jwk(self):
        p = self.tmp / "secrets" / "gateway-signing.jwk"
        r = self.gen(p)
        self.assertEqual(r.returncode, 0, r.stderr)
        jwk = json.loads(p.read_text())
        self.assertEqual((jwk["kty"], jwk["crv"]), ("OKP", "Ed25519"))
        for k in ("x", "d"):
            self.assertEqual(len(base64.urlsafe_b64decode(jwk[k] + "=")), 32, k)
        self.assertRegex(jwk["kid"], r"^gw-[0-9a-f]{16}$")
        self.assertNotIn(jwk["d"], r.stdout + r.stderr, "the private key is never printed")
        self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o644)  # the container's non-root user must read it
        self.assertEqual(stat.S_IMODE(p.parent.stat().st_mode), 0o700)  # other host users can't

    def test_OM_05_keygen_never_overwrites(self):
        p = self.tmp / "gateway-signing.jwk"
        self.gen(p)
        first = p.read_text()
        r = self.gen(p)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(p.read_text(), first)

    def test_OM_05_two_keys_differ(self):
        a, b = self.tmp / "a.jwk", self.tmp / "b.jwk"
        self.gen(a)
        self.gen(b)
        self.assertNotEqual(json.loads(a.read_text())["d"], json.loads(b.read_text())["d"])


class ComposeWiring(unittest.TestCase):
    def test_OM_05_gateway_gets_key_read_only_and_token_from_env(self):
        g = gateway_block()
        self.assertIn("GATEWAY_SIGNING_JWK_PATH: /run/secrets/gateway-signing.jwk", g)
        self.assertRegex(g, r"\.\./\.\./secrets/gateway-signing\.jwk:/run/secrets/gateway-signing\.jwk:ro")
        self.assertIn("GATEWAY_OPERATOR_TOKEN: ${GATEWAY_OPERATOR_TOKEN:?run make bootstrap}", g)

    def test_OM_05_bootstrap_makes_the_key(self):
        mk = (ROOT / "Makefile").read_text()
        block = mk.split("\nbootstrap:", 1)[1].split("\n\n", 1)[0]
        self.assertIn("KeyGen.java secrets/gateway-signing.jwk", block)


if __name__ == "__main__":
    unittest.main()
