"""SH-02 contracts_check (§9, golden rules 3 + 4): schemas valid, examples validate, invalid examples fail,
no float money, no truth outside privileged shapes. Stdlib; the script itself runs under `uv run --with`."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "https://json-schema.org/draft/2020-12/schema"
BASE = "https://secondline.invalid/contracts/1/"
CMD = ["uv", "run", "-q", "--with", "jsonschema==4.26.0", "--with", "pyyaml==6.0.3", "python",
       str(ROOT / "scripts/contracts_check.py")]


def schema(path: str, props: dict, **extra) -> dict:
    return {"$schema": SCHEMA, "$id": BASE + path, "type": "object", "additionalProperties": False,
            "properties": props, **extra}


@unittest.skipUnless(shutil.which("uv") or os.environ.get("CI"), "uv not installed")  # CI: fail, never skip
class ContractsCheck(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "VERSION").write_text("1.0.0\n")
        self.write("money.schema.json", schema("money.schema.json", {"amount": {"type": "string"}},
                                               required=["amount"]))
        self.write("examples/money.json", {"x-validates": "money.schema.json", "amount": "1.00"})
        self.write("examples/invalid/money_float.json", {"x-validates": "money.schema.json", "amount": 1.5})

    def tearDown(self):
        shutil.rmtree(self.root)

    def write(self, rel: str, doc):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc, indent=1) + "\n")

    def check(self) -> subprocess.CompletedProcess:
        return subprocess.run(CMD + ["--root", str(self.root)], capture_output=True, text=True, timeout=120)

    def assertFails(self, needle: str):
        r = self.check()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(needle, r.stdout)

    def test_SH_02_valid_tree_passes(self):
        r = self.check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_SH_02_number_money_rejected(self):
        self.write("money.schema.json", schema("money.schema.json", {"amount": {"type": "number"}}))
        self.assertFails("float money")

    def test_SH_02_truth_field_rejected(self):
        self.write("tool.schema.json", schema("tool.schema.json", {"truth_ref": {"type": "string"}}))
        self.assertFails("truth field")

    def test_SH_02_truth_field_allowed_when_privileged(self):
        self.write("scenario/truth.schema.json", schema("scenario/truth.schema.json", {"truth_ref": {"type": "string"}},
                                                        **{"x-privileged": True}))
        self.assertEqual(self.check().returncode, 0)

    def test_SH_02_example_mismatch_rejected(self):
        self.write("examples/money.json", {"x-validates": "money.schema.json", "amount": 2})
        self.assertFails("examples/money.json")

    def test_SH_02_invalid_example_that_validates_rejected(self):
        self.write("examples/invalid/money_ok.json", {"x-validates": "money.schema.json", "amount": "3"})
        self.assertFails("examples/invalid/money_ok.json")

    def test_SH_02_missing_id_rejected(self):
        s = schema("money.schema.json", {"amount": {"type": "string"}})
        del s["$id"]
        self.write("money.schema.json", s)
        self.assertFails("$id")

    def test_SH_02_example_can_target_a_definition(self):
        self.write("common.schema.json", {"$schema": SCHEMA, "$id": BASE + "common.schema.json",
                                          "$defs": {"ref": {"type": "object", "required": ["v"]}}})
        self.write("examples/ok_ref.json", {"x-validates": "common.schema.json#/$defs/ref", "v": 1})
        self.assertEqual(self.check().returncode, 0)
        self.write("examples/bad_ref.json", {"x-validates": "common.schema.json#/$defs/ref"})
        self.assertFails("examples/bad_ref.json")

    def test_SH_02_truth_variants_rejected(self):
        for name in ("rootCause", "root_cause_label", "break_type", "ground_truth", "allowed_outcomes",
                     "required_evidence_ids", "injected_flag", "hidden_label", "canary"):
            with self.subTest(name=name):
                self.write("t.schema.json", schema("t.schema.json", {name: {"type": "string"}}))
                self.assertFails("truth field")

    def test_SH_02_truth_in_enum_or_required_rejected(self):
        self.write("t.schema.json", schema("t.schema.json", {"k": {"enum": ["OK", "ROOT_CAUSE_TIMING"]}}))
        self.assertFails("truth field")

    def test_SH_02_canary_string_anywhere_rejected(self):
        self.write("examples/money.json", {"x-validates": "money.schema.json", "amount": "1", "note": "SLCANARY-ab12"})
        self.assertFails("SLCANARY")

    def test_SH_02_canary_allowed_where_truth_lives(self):
        # ADR-015: truth carries a canary; invalid examples prove rejection; a pattern can forbid it.
        self.write("scenario/truth.schema.json", schema("scenario/truth.schema.json", {"canary_id": {"type": "string"}},
                                                        **{"x-privileged": True, "description": "has SLCANARY-x"}))
        self.write("examples/truth.json", {"x-validates": "scenario/truth.schema.json", "canary_id": "SLCANARY-ab12"})
        self.write("examples/invalid/money_canary.json", {"x-validates": "money.schema.json", "amount": 2,
                                                          "note": "SLCANARY-ab12"})
        self.write("bundle.schema.json", schema("bundle.schema.json", {"note": {"type": "string",
                                                "not": {"pattern": "SLCANARY-"}}}))
        r = self.check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def priv(self):
        self.write("scenario/truth.schema.json", schema("scenario/truth.schema.json", {"k": {"type": "string"}},
                                                        **{"x-privileged": True}))
        self.write("common.schema.json", {"$schema": SCHEMA, "$id": BASE + "common.schema.json",
                                          "$defs": {"break_type": {"enum": ["B1_TIMING_CUTOFF"]}}})

    def test_SH_02_visible_schema_cannot_ref_privileged(self):
        self.priv()
        self.write("tool.schema.json", schema("tool.schema.json", {"x": {"$ref": "scenario/truth.schema.json"}}))
        self.assertFails("privileged")

    def test_SH_02_visible_schema_cannot_ref_break_type(self):
        self.priv()
        self.write("tool.schema.json", schema("tool.schema.json", {"x": {"$ref": "common.schema.json#/$defs/break_type"}}))
        self.assertFails("privileged")

    def test_SH_02_privileged_ref_bypasses_rejected(self):
        self.priv()
        for ref in (BASE + "scenario/truth.schema.json",                 # absolute $id URL
                    "common.schema.json#/%24defs/break_type",            # percent-encoded pointer
                    "common.schema.json#/$defs/break_type/enum",         # pointer into the definition
                    "./scenario/../scenario/truth.schema.json"):         # non-normalised path
            with self.subTest(ref=ref):
                self.write("tool.schema.json", schema("tool.schema.json", {"x": {"$ref": ref}}))
                self.assertFails("privileged")

    def test_SH_02_ref_outside_tree_fails_closed(self):
        self.write("tool.schema.json", schema("tool.schema.json", {"x": {"$ref": "../../elsewhere.schema.json"}}))
        self.assertFails("outside the contracts tree")

    def test_SH_02_privileged_schema_may_ref_break_type(self):
        self.priv()
        self.write("scenario/truth.schema.json", schema("scenario/truth.schema.json",
                   {"b": {"$ref": "../common.schema.json#/$defs/break_type"}}, **{"x-privileged": True}))
        r = self.check()
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_SH_02_self_declared_privileged_rejected(self):
        self.write("tool.schema.json", schema("tool.schema.json", {"root_cause": {"type": "string"}},
                                              **{"x-privileged": True}))
        self.assertFails("not on the privileged list")

    def test_SH_02_non_hex_canary_rejected(self):
        self.write("examples/money.json", {"x-validates": "money.schema.json", "amount": "1", "n": "SLCANARY-zzzz"})
        self.assertFails("SLCANARY")

    def test_SH_02_canary_in_plain_pattern_rejected(self):
        self.write("money.schema.json", schema("money.schema.json", {"amount": {"type": "string",
                                               "pattern": "^SLCANARY-ab12$"}}))
        self.assertFails("SLCANARY")

    def test_SH_02_bad_version_rejected(self):
        (self.root / "VERSION").write_text("v1\n")
        self.assertFails("VERSION")


if __name__ == "__main__":
    unittest.main()
