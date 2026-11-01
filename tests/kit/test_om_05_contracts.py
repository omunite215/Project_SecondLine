"""OM-05 contracts 2.1.0 (§8 §11, ADR-013 ADR-014, REQ-004 REQ-005): a run request carries what the run token and
the ledger's run registry need (scenario_id, manifest_ref), and every gateway decision — denies included — has
one append-only shape the ledger stores. Stdlib only, like the kit."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
C = ROOT / "packages/contracts"


def load(rel: str) -> dict:
    return json.loads((C / rel).read_text())


class RunRequest(unittest.TestCase):
    def test_OM_05_run_request_names_scenario_and_manifest(self):
        s = load("runs/run_request.schema.json")
        self.assertEqual(s["required"], ["ns", "controls", "agent_id", "scenario_id", "manifest_ref"])
        self.assertEqual(s["properties"]["scenario_id"]["$ref"], "../common.schema.json#/$defs/opaque_id")
        self.assertEqual(s["properties"]["manifest_ref"]["$ref"], "../common.schema.json#/$defs/manifest_ref")

    def test_OM_05_one_manifest_ref_definition(self):
        # The gateway forwards manifest_ref to the ledger registry; one definition, so they can't disagree.
        d = load("common.schema.json")["$defs"]["manifest_ref"]
        admin = (C / "openapi/ledger-admin.yaml").read_text()
        self.assertIn("manifest_ref: {$ref: '../common.schema.json#/$defs/manifest_ref'", admin)
        for bad in ("../x.json", "data/generated/eval/truth/x.json", "x/truth/y.json"):
            self.assertTrue(any(re.search(p, bad) for p in [n["pattern"] for n in d["not"]["anyOf"]]), bad)


class DecisionLog(unittest.TestCase):
    def test_OM_05_decision_log_entry_shape(self):
        s = load("runs/decision_log_entry.schema.json")
        self.assertFalse(s["additionalProperties"])
        self.assertEqual(s["required"], ["decision_id", "run_id", "tool", "decision", "controls", "stage", "at"])
        self.assertEqual(s["properties"]["decision"]["enum"], ["ALLOW", "DENY", "REVIEW_REQUIRED"])
        self.assertEqual(s["properties"]["stage"]["enum"],
                         ["token", "binding", "schema", "guard", "policy", "ledger", "routed"])
        self.assertEqual(s["properties"]["error_code"]["$ref"], "../error_response.schema.json#/properties/error_code")
        self.assertEqual(s["properties"]["tool"]["$ref"], "../common.schema.json#/$defs/tool_name")

    def test_OM_05_tool_names_are_the_index(self):
        names = load("common.schema.json")["$defs"]["tool_name"]["enum"]
        self.assertEqual(sorted(names), sorted(load("tools/INDEX.json")["tools"]))

    def test_OM_05_ledger_accepts_decisions(self):
        text = (C / "openapi/ledger-internal.yaml").read_text()
        block = text.split("  /internal/v1/ns/{ns}/decisions:\n", 1)[1].split("\n  /", 1)[0]
        self.assertRegex(block, r"(?m)^    post:")
        self.assertIn("'../runs/decision_log_entry.schema.json'", block)
        for status in ("'201'", "'403'", "'422'", "'503'"):
            self.assertIn(status, block, status)

    def test_OM_05_version(self):
        self.assertEqual((C / "VERSION").read_text().strip(), "2.1.0")


if __name__ == "__main__":
    unittest.main()
