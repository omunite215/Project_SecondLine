"""SH-02 §10 tool schemas: exactly the spec's tools, nothing from the "not exposed" list, writes return receipts,
evidence is marked untrusted. Stdlib only."""
import json
import re
import unittest
from pathlib import Path

C = Path(__file__).resolve().parents[2] / "packages/contracts"
SPEC_TOOLS = {"list_breaks", "get_break", "read_trade", "read_bookings", "read_positions", "read_custodian_statement",
              "read_settlement_status", "read_reference_data", "read_corporate_actions", "read_fx_snapshot",
              "read_evidence", "request_counterparty_clarification", "propose_classification",
              "propose_booking_correction", "propose_corporate_action", "propose_adjustment", "escalate_break",
              "get_action_status", "get_approval_status"}
WRITES = {"propose_classification": "CLASSIFY", "propose_booking_correction": "BOOKING_CORRECTION",
          "propose_corporate_action": "CORPORATE_ACTION", "propose_adjustment": "ADJUSTMENT",
          "escalate_break": "ESCALATE"}


def schema(tool: str, kind: str) -> dict:
    return json.loads((C / f"tools/{tool}.{kind}.schema.json").read_text())


class Tools(unittest.TestCase):
    def test_SH_02_every_spec_tool_has_both_schemas(self):
        found = {p.name.split(".")[0] for p in (C / "tools").glob("*.schema.json")}
        self.assertEqual(found, SPEC_TOOLS)
        for t in SPEC_TOOLS:
            for kind in ("input", "output"):
                self.assertTrue((C / f"tools/{t}.{kind}.schema.json").exists(), (t, kind))
        index = json.loads((C / "tools/INDEX.json").read_text())
        self.assertEqual(set(index["tools"]), SPEC_TOOLS)

    def test_SH_02_no_forbidden_tool(self):
        # §10 "not exposed": SQL, journal edit, reference-data modification, account creation, oracle, raw Kafka,
        # approval, filesystem/network.
        bad = re.compile(r"sql|journal|update_reference|edit_|create_account|oracle|truth|publish|kafka|approve|"
                         r"file|http|shell|debug|admin")
        for t in SPEC_TOOLS | {p.name.split(".")[0] for p in (C / "tools").glob("*.json")}:
            self.assertIsNone(bad.search(t), t)

    def test_SH_02_write_tools_return_receipts_and_pin_type(self):
        for tool, action_type in WRITES.items():
            out = schema(tool, "output")
            self.assertEqual(out["$ref"], "../receipts/decision_receipt.schema.json", tool)
            inp = schema(tool, "input")
            self.assertEqual(inp["allOf"][0]["$ref"], "../actions/proposed_action.schema.json", tool)
            self.assertEqual(inp["allOf"][1]["properties"]["type"]["const"], action_type, tool)

    def test_SH_02_evidence_is_marked_untrusted(self):
        props = schema("read_evidence", "output")["properties"]
        self.assertEqual(props["untrusted"], {"const": True})

    def test_SH_02_every_input_is_run_scoped(self):
        for t in SPEC_TOOLS - set(WRITES):
            self.assertIn("run_id", schema(t, "input")["required"], t)

    def test_SH_02_reads_never_return_reason_labels(self):
        # reason_code is the agent's claim (graded); no read tool may hand the agent those labels.
        labels = set(json.loads((C / "actions/proposed_action.schema.json").read_text())["properties"]["reason_code"]["enum"])
        for t in SPEC_TOOLS - set(WRITES) - {"get_action_status"}:
            text = (C / f"tools/{t}.output.schema.json").read_text()
            self.assertFalse([l for l in labels if f'"{l}"' in text], t)

    def test_SH_02_gateway_openapi_types_each_tool(self):
        text = (C / "openapi/gateway-tools.yaml").read_text()
        for t in SPEC_TOOLS:
            self.assertIn(f"/v1/runs/{{runId}}/tools/{t}:", text, t)
            self.assertIn(f"../tools/{t}.output.schema.json", text, t)

    def test_SH_02_every_tool_has_examples(self):
        for t in SPEC_TOOLS:
            for kind in ("input", "output"):
                self.assertTrue((C / f"examples/tools/{t}.{kind}.json").exists(), (t, kind))


if __name__ == "__main__":
    unittest.main()
