"""OM-04 ADR-015 SEC (until OM-07): the ledger's admin and internal routes have no realm authentication yet,
so compose may publish the ledger only on loopback (the runner on the host needs the admin API), never on
all interfaces. OM-07 replaces this guard with authentication + the bypass test. Stdlib only."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ROOT / "infra/compose/docker-compose.yml"


def service_block(name: str) -> str:
    text = COMPOSE.read_text()
    m = re.search(rf"(?ms)^  {name}:\n(.*?)(?=^  \S|\Z)", text)
    assert m, name
    return m.group(1)


class LedgerExposure(unittest.TestCase):
    def test_OM_04_ledger_published_on_loopback_only(self):
        ports = re.findall(r'"([^"]*:\d+:\d+|\d+:\d+|\d+)"', " ".join(
            l for l in service_block("ledger").splitlines() if "ports" in l))
        self.assertTrue(ports, "expected the loopback port the runner uses")
        for p in ports:
            self.assertTrue(p.startswith("127.0.0.1:"), f"ledger port {p} must bind 127.0.0.1 until OM-07")


if __name__ == "__main__":
    unittest.main()
