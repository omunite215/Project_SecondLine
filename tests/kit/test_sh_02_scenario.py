"""SH-02 Kunal's half: scenario manifest / run manifest / world bundle / ns export / truth / attack pack + eval
OpenAPI (§5 §9 §14 §15, ADR-015, ADR-016 B1–B8 table, T-DOM-03, REQ-004/005/007, golden rule 4).
Bad input is proven by examples/invalid/** (contracts_check requires each to FAIL); these tests pin which
invalid cases exist, which shapes are privileged, and that no canary or truth name escapes. Stdlib only."""
import json
import re
import unittest
from pathlib import Path

C = Path(__file__).resolve().parents[2] / "packages/contracts"
CANARY = re.compile(r"SLCANARY-")
TRUTH_NAMES = re.compile(r"^(truth|truth_ref|root_cause|expected_state_delta|oracle_.*|canary|break_type|seed)$")
PRIVILEGED = ("scenario/run_manifest.schema.json", "scenario/truth.schema.json", "attacks/attack_pack.schema.json")
VISIBLE = ("scenario/manifest.schema.json", "scenario/world_bundle.schema.json", "scenario/ns_export.schema.json")
BREAK_TYPES = ["B1_TIMING_CUTOFF", "B2_QUANTITY_MISMATCH", "B3_PRICE_ROUNDING", "B4_FX_REVALUATION",
               "B5_MISSING_OR_DUPLICATE_TRADE", "B6_CORPORATE_ACTION", "B7_SETTLEMENT_SHORTFALL", "B8_SSI_MISMATCH"]


def load(rel: str) -> dict:
    return json.loads((C / rel).read_text())


def property_names(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "properties" and isinstance(v, dict):
                yield from v
            yield from property_names(v)
    elif isinstance(node, list):
        for v in node:
            yield from property_names(v)


class Scenario(unittest.TestCase):
    def test_SH_02_T_DOM_03_privileged_shapes_are_marked(self):
        for rel in PRIVILEGED:
            self.assertIs(load(rel).get("x-privileged"), True, rel)
        for rel in VISIBLE:
            self.assertNotIn("x-privileged", load(rel), rel)

    def test_SH_02_T_DOM_03_visible_shapes_carry_no_truth_names(self):
        # Stricter than contracts_check: also canary, break_type and seed (they regenerate or label the truth).
        for rel in VISIBLE:
            bad = sorted(n for n in property_names(load(rel)) if TRUTH_NAMES.match(n))
            self.assertEqual(bad, [], rel)

    def test_SH_02_run_manifest_holds_the_s9_fields(self):
        m = load("scenario/run_manifest.schema.json")
        for f in ("scenario_id", "schema_version", "generator_version", "seed", "split", "break_type",
                  "pressure_level", "injection_condition", "snapshot_hash", "source_snapshot_refs", "truth_ref",
                  "initial_state_ref"):
            self.assertIn(f, m["required"], f)
        self.assertEqual(m["properties"]["break_type"]["$ref"], "../common.schema.json#/$defs/break_type")
        self.assertEqual(m["properties"]["pressure_level"]["enum"], ["L0", "L1", "L2", "L3"])

    def test_SH_02_break_type_enum_is_b1_to_b8(self):
        self.assertEqual(load("common.schema.json")["$defs"]["break_type"]["enum"], BREAK_TYPES)

    def test_SH_02_C4_truth_root_cause_reuses_reason_code(self):
        ref = "../common.schema.json#/$defs/reason_code"
        self.assertEqual(load("actions/proposed_action.schema.json")["properties"]["reason_code"]["$ref"], ref)
        brk = load("scenario/truth.schema.json")["$defs"]["break_truth"]["properties"]
        self.assertEqual(brk["root_cause"]["$ref"], ref)

    def test_SH_02_truth_requires_canary_and_s5_oracle_fields(self):
        t = load("scenario/truth.schema.json")
        self.assertIn("canary", t["required"])
        self.assertTrue(t["properties"]["canary"]["pattern"].startswith("^SLCANARY-"))
        brk = t["$defs"]["break_truth"]["required"]
        for f in ("break_id", "break_type", "root_cause", "causal_event_ids", "allowed_outcomes",
                  "required_evidence_ids", "forbidden_outcomes", "approval_requirements", "expected_state_delta",
                  "escalation_if_insufficient_evidence", "severity"):
            self.assertIn(f, brk, f)

    def test_SH_02_no_canary_in_examples_of_visible_shapes(self):
        for f in sorted((C / "examples").rglob("*.json")):
            doc = json.loads(f.read_text())
            target = doc.get("x-validates", "").partition("#")[0] if isinstance(doc, dict) else ""
            if target in PRIVILEGED or "invalid" in f.parts:  # invalid/** is proven rejected by contracts_check
                continue
            self.assertIsNone(CANARY.search(f.read_text()), f.relative_to(C).as_posix())

    def test_SH_02_attack_pack_examples_are_dev_only(self):
        # Golden rule 5: no eval attack content in the repo's contracts.
        for f in sorted((C / "examples").rglob("*.json")):
            doc = json.loads(f.read_text())
            if doc.get("x-validates") == "attacks/attack_pack.schema.json" and "invalid" not in f.parts:
                self.assertEqual(doc["split"], "dev", f.name)

    def test_SH_02_required_examples_exist(self):
        for rel in ("scenario/manifest.json", "scenario/run_manifest.json", "scenario/world_bundle_minimal.json",
                    "scenario/ns_export_minimal.json", "scenario/truth_b3.json", "scenario/truth_b7.json",
                    "attacks/attack_pack_dev.json"):
            self.assertTrue((C / "examples" / rel).exists(), rel)

    def test_SH_02_invalid_cases_exist(self):
        for name in ("manifest_with_truth_ref", "manifest_with_break_type", "world_bundle_with_root_cause",
                     "world_bundle_float_price", "world_bundle_evidence_with_canary",
                     "world_bundle_snapshot_without_license", "truth_without_canary",
                     "truth_unknown_break_type", "truth_float_delta", "attack_pack_unknown_family",
                     "ns_export_float_balance", "run_manifest_injection_without_pack",
                     "run_manifest_pack_without_injection", "world_bundle_instrument_name_with_canary",
                     "world_bundle_license_with_canary", "world_bundle_evidence_key_with_break_label"):
            self.assertTrue((C / f"examples/invalid/{name}.json").exists(), name)

    def test_SH_02_T_DOM_03_only_privileged_shapes_ref_break_type(self):
        # break_type lives in common.schema.json; a $ref from any other shape would leak the root-cause label.
        for f in sorted(C.rglob("*.schema.json")):
            rel = f.relative_to(C).as_posix()
            if rel in PRIVILEGED or rel == "common.schema.json":
                continue
            self.assertNotIn("$defs/break_type", f.read_text(), rel)

    def test_SH_02_eval_openapi_error_codes_come_from_errors_json(self):
        errors = {e["code"]: e for e in load("errors.json")["errors"]}
        text = (C / "openapi/eval.yaml").read_text()
        codes = re.search(r"code:\n\s+enum: \[([A-Z_, ]+)\]", text)
        self.assertIsNotNone(codes, "Error.code must be an enum")
        for code in (c.strip() for c in codes.group(1).split(",")):
            self.assertIn(code, errors)
            self.assertFalse(errors[code].get("grader_only", False), code)  # never ORACLE_MISMATCH

    def test_SH_02_eval_openapi_skeleton(self):
        text = (C / "openapi/eval.yaml").read_text()
        self.assertRegex(text, r"(?m)^openapi: 3\.1\.\d+$")
        for path in ("/v1/runs:", "/v1/runs/{run_id}:", "/v1/runs/{run_id}/grade:"):
            self.assertIn(path, text)
        self.assertIn("Idempotency-Key", text)
        # Graded outcomes only, after grading (ADR-015): the eval API never returns raw truth.
        for name in ("truth_ref", "root_cause", "expected_state_delta", "SLCANARY"):
            self.assertNotIn(name, text)


if __name__ == "__main__":
    unittest.main()
