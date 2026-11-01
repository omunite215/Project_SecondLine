"""OM-04 T-EVAL-03 ADR-015 (Amendment 1): the state-hash vector re-derives in Python, independently of the
ledger's Java JCS, so the grader (KG-06) and the ledger agree on what "same state" means. Stdlib only."""
import hashlib
import json
import unittest
from pathlib import Path

C = Path(__file__).resolve().parents[2] / "packages/contracts"
VEC = C / "test-vectors/state_hash/minimal.json"


def jcs(doc) -> bytes:
    # RFC 8785 for documents of strings, integers, arrays and objects only (golden rule 3: no JSON numbers
    # with fractions anywhere in these documents).
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha(doc) -> str:
    return "sha256:" + hashlib.sha256(jcs(doc)).hexdigest()


class StateHashVector(unittest.TestCase):
    def setUp(self):
        self.v = json.loads(VEC.read_text())

    def test_OM_04_T_EVAL_03_snapshot_hash_is_bundle_jcs(self):
        bundle = json.loads((C / self.v["bundle"]).read_text())
        bundle.pop("x-validates")
        self.assertEqual(sha(bundle), self.v["snapshot_hash"])

    def test_OM_04_T_EVAL_03_state_hash_is_export_jcs_without_ns(self):
        export = self.v["export_without_ns"]
        self.assertNotIn("ns", export)
        self.assertEqual(export["snapshot_hash"], self.v["snapshot_hash"])
        self.assertEqual(sha(export), self.v["state_hash"])

    def test_OM_04_T_EVAL_03_vector_matches_contract_example(self):
        ex = json.loads((C / "examples/scenario/ns_export_minimal.json").read_text())
        for k in ("x-validates", "ns", "snapshot_hash"):
            ex.pop(k)
        got = dict(self.v["export_without_ns"])
        got.pop("snapshot_hash")
        self.assertEqual(got, ex)


if __name__ == "__main__":
    unittest.main()
