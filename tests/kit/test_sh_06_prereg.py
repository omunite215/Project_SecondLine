"""SH-06 (§14, U6, REQ-007 REQ-014): the prereg draft defines every MET with a numerator, a denominator and a unit,
and fixes the H1 opportunity, H2 latency span, pass^k estimator and cluster structure before any run.
Stdlib only, like the kit: python3 -m unittest discover -s tests/kit"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "experiments/prereg/preregistration.md"


def metrics_section() -> str:
    text = PREREG.read_text()
    m = re.search(r"^## Metrics\b(.*?)(?=^## |\Z)", text, re.S | re.M)
    assert m, "preregistration.md has no '## Metrics' section"
    return m.group(1)


def met_blocks(section: str) -> dict[str, str]:
    parts = re.split(r"^### (MET-\d\d)\b", section, flags=re.M)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts), 2)}


class Prereg(unittest.TestCase):
    def test_SH_06_draft_is_not_in_frozen_tree(self):
        self.assertTrue(PREREG.is_file())
        self.assertIn("DRAFT", PREREG.read_text().splitlines()[0])

    def test_SH_06_all_twelve_metrics_have_numerator_denominator_unit(self):
        blocks = met_blocks(metrics_section())
        self.assertEqual(sorted(blocks), [f"MET-{i:02d}" for i in range(1, 13)])
        for met, body in blocks.items():
            for field in ("Numerator", "Denominator", "Unit"):
                self.assertRegex(body, rf"\*\*{field}:\*\*\s*\S", f"{met} lacks {field}")

    def test_SH_06_zero_denominator_rule(self):
        self.assertIn("n/a (0 opportunities)", metrics_section())

    def test_SH_06_h1_opportunity_h2_span_passk_clusters(self):
        s = metrics_section()
        self.assertIn("applicable opportunity", s)
        self.assertIn("gateway.onpath", s)
        self.assertIn("C(c, k) / C(n, k)", s)
        self.assertRegex(s, r"not pass@k")
        self.assertRegex(s, r"cluster bootstrap.*by scenario", )


if __name__ == "__main__":
    unittest.main()
