"""SH-02 x ADR-017 (§5 §8 §9, REQ-006, I5, T-DOM-03, T-DOM-04): the evidence vocabulary is ADR-017's closed set;
a world-bundle evidence record carries only the field keys allowed for its kind (an allowlist, so a cause hint such
as `root_cause_hint` can't ride in a field name); INTERNAL_BOOKING is cited from ledger ids, never a bundle record;
opaque ids can't reveal a split. Structure checks are stdlib; the validator-backed class runs under `uv run --with`."""
import json
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
C = ROOT / "packages/contracts"
ADR_017_KINDS = {"INTERNAL_BOOKING", "BROKER_CONFIRM", "CUSTODIAN_STATEMENT", "NOSTRO_STATEMENT", "SETTLEMENT_STATUS",
                 "CA_NOTICE", "SSI_RECORD", "FX_RATE_NOTICE", "COUNTERPARTY_MESSAGE"}
CAUSE_WORDS = re.compile(r"truth|cause|root|expected|oracle|canary|break|seed|duplicate|shortfall|mismatch|error|"
                         r"wrong|label|hint|split|^b[1-8]", re.I)
SPLIT_WORDS = ("dev", "eval", "blind", "test")
# new invalid example -> the instance path its rejection must point at (the intended reason, not any reason)
INVALID = {"world_bundle_evidence_key_root_cause_hint": ["evidence", 0, "fields"],
           "world_bundle_evidence_key_outside_kind_allowlist": ["evidence", 1, "fields"],
           "world_bundle_evidence_internal_booking_record": ["evidence", 0, "kind"],
           "world_bundle_record_id_with_split": ["evidence", 0, "record_id"],
           "world_bundle_settlement_quantity_free_text": ["evidence", 2, "fields", "quantity"],
           "world_bundle_settlement_status_outside_enum": ["evidence", 2, "fields", "status"],
           "world_bundle_source_system_with_split": ["evidence", 0, "source_system"]}
TYPED = {"quantity", "price", "gross", "amount", "debit_amount", "credit_amount", "balance", "rate", "ratio_new",
         "ratio_old", "cash_in_lieu_price", "currency", "base_currency", "quote_currency", "isin", "trade_ref", "side",
         "status", "status_code", "event_type", "trade_date", "settle_date", "value_date", "as_of", "ex_date",
         "record_date", "pay_date", "effective_date", "cutoff_time"}


def load(rel: str) -> dict:
    return json.loads((C / rel).read_text())


def allowlists() -> dict[str, set[str]]:
    rec = load("scenario/world_bundle.schema.json")["$defs"]["evidence_record"]
    out = {}
    for rule in rec.get("allOf", []):
        kind = rule["if"]["properties"]["kind"]["const"]
        out[kind] = set(rule["then"]["properties"]["fields"]["propertyNames"]["enum"])
    return out


class EvidenceVocabulary(unittest.TestCase):
    def test_SH_02_T_DOM_04_evidence_kind_is_the_adr_017_closed_set(self):
        self.assertEqual(set(load("common.schema.json")["$defs"]["evidence_kind"]["enum"]), ADR_017_KINDS)

    def test_SH_02_T_DOM_04_every_bundle_kind_has_a_field_allowlist(self):
        # INTERNAL_BOOKING refs resolve to trades / journals / movements, so the bundle holds no such evidence record.
        self.assertEqual(set(allowlists()), ADR_017_KINDS - {"INTERNAL_BOOKING"})

    def test_SH_02_T_DOM_03_allowlisted_field_keys_carry_no_cause_words(self):
        for kind, keys in allowlists().items():
            for key in keys:
                self.assertIsNone(CAUSE_WORDS.search(key), f"{kind}.{key}")

    def test_SH_02_T_DOM_03_value_keys_are_typed_not_free_text(self):
        # Golden rule 3 + leakage: a number, date or code can't hide a cause as free text ("short 100").
        rec = load("scenario/world_bundle.schema.json")["$defs"]["evidence_record"]
        for rule in rec["allOf"]:
            fields = rule["then"]["properties"]["fields"]
            for key in set(fields["propertyNames"]["enum"]) & TYPED:
                self.assertIn(key, fields.get("properties", {}), f"{rule['if']['properties']['kind']['const']}.{key}")

    def test_SH_02_T_DOM_03_bundle_record_kind_excludes_internal_booking(self):
        kind = load("common.schema.json")["$defs"]["evidence_record_kind"]
        self.assertEqual(kind["$ref"], "#/$defs/evidence_kind")
        self.assertIn("INTERNAL_BOOKING", kind["not"]["enum"])

    def test_SH_02_T_DOM_03_opaque_id_forbids_split_words(self):
        opaque = load("common.schema.json")["$defs"]["opaque_id"]
        forbid = re.compile(opaque["not"]["pattern"])
        for word in SPLIT_WORDS:
            self.assertTrue(forbid.search(f"evd_000{word.upper()}01"), word)
            self.assertTrue(forbid.search(f"{word}_00000001"), word)
        for ok in ("evd_0000E001", "trd_0000B001", "brk_0000F001", "act_9fK2mQ7xZ1"):
            self.assertIsNone(forbid.search(ok), ok)

    def test_SH_02_new_examples_exist(self):
        for name in INVALID:
            self.assertTrue((C / f"examples/invalid/{name}.json").exists(), name)
        kinds = {e["kind"] for e in load("examples/scenario/world_bundle_minimal.json")["evidence"]}
        self.assertIn("SETTLEMENT_STATUS", kinds)


VALIDATE = r"""
import json, sys
from pathlib import Path
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
root = Path(sys.argv[1])
schemas = {f.relative_to(root).as_posix(): json.loads(f.read_text()) for f in root.rglob("*.schema.json")}
reg = Registry().with_resources((d["$id"], Resource.from_contents(d)) for d in schemas.values())
out = {}
for rel in sys.argv[2:]:
    doc = json.loads((root / rel).read_text())
    v = Draft202012Validator(schemas[doc.pop("x-validates")], registry=reg)
    out[rel] = [list(e.absolute_path) for e in v.iter_errors(doc)]
print(json.dumps(out))
"""


@unittest.skipUnless(shutil.which("uv") or os.environ.get("CI"), "uv not installed")  # CI: fail, never skip
class EvidenceRejectedForTheIntendedReason(unittest.TestCase):
    def errors(self, rels: list[str]) -> dict[str, list]:
        cmd = ["uv", "run", "-q", "--with", "jsonschema==4.26.0", "python", "-c", VALIDATE, str(C), *rels]
        return json.loads(subprocess.run(cmd, check=True, capture_output=True, text=True).stdout)

    def test_SH_02_T_DOM_03_invalid_evidence_fails_at_the_intended_path(self):
        got = self.errors([f"examples/invalid/{n}.json" for n in INVALID])
        for name, path in INVALID.items():
            paths = got[f"examples/invalid/{name}.json"]
            self.assertIn(path, paths, f"{name}: rejected only at {paths}")

    def test_SH_02_T_DOM_04_minimal_bundle_with_settlement_status_validates(self):
        self.assertEqual(self.errors(["examples/scenario/world_bundle_minimal.json"]),
                         {"examples/scenario/world_bundle_minimal.json": []})


if __name__ == "__main__":
    unittest.main()
