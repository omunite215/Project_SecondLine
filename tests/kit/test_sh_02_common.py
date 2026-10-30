"""SH-02 common definitions (§9, golden rule 3): decimals are strings that codegen still types as Decimal.
Stdlib only, like the kit: python3 -m unittest discover -s tests/kit"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFS = json.loads((ROOT / "packages/contracts/common.schema.json").read_text())["$defs"]


class Common(unittest.TestCase):
    def test_SH_02_decimals_carry_format_for_codegen(self):
        # KG-01: datamodel-codegen maps `type: string, format: decimal` → Decimal; pattern-only → str.
        for name in ("decimal", "quantity"):
            self.assertEqual((DEFS[name]["type"], DEFS[name].get("format")), ("string", "decimal"), name)

    def test_SH_02_currencies_match_adr_016(self):
        self.assertEqual(DEFS["currency"]["enum"], ["USD", "EUR", "GBP", "CHF", "JPY"])


if __name__ == "__main__":
    unittest.main()
