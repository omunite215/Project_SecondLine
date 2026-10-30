"""SH-08 §9 §12 (REQ-009, T-SEC-05, SEC-09, ADR-012): receipt canonicalization + hash-chain vectors.

Expected values come from scripts/receipt_vectors.py (stdlib JCS + a reference chain verifier). OM-14
(Java) and KG-12 (audit-verifier) must reproduce them. Signature vectors wait for ADR-018 (SH-09)."""
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VEC = ROOT / "packages/contracts/test-vectors/receipts"
SCHEMA = ROOT / "packages/contracts/receipts/decision_receipt.schema.json"
GEN = ROOT / "scripts/receipt_vectors.py"
UV = ["uv", "run", "-q", "--with", "jsonschema==4.26.0", "--with", "pyyaml==6.0.3", "python"]

spec = importlib.util.spec_from_file_location("receipt_vectors", GEN)
assert spec is not None and spec.loader is not None, GEN
rv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rv)


def load(name: str) -> dict:
    return json.loads((VEC / name).read_text(encoding="utf-8"))


class Jcs(unittest.TestCase):
    def test_SH_08_vectors_current(self):
        r = subprocess.run(["python3", str(GEN), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_SH_08_jcs_cases_recompute(self):
        cases = load("jcs.json")["cases"]
        self.assertGreaterEqual(len(cases), 12)
        for c in cases:
            canonical = rv.jcs(rv.parse(c["input"]))
            self.assertEqual(canonical, c["canonical"], c["name"])
            self.assertEqual(rv.sha256(canonical), c["sha256"], c["name"])

    def test_SH_08_rfc8785_sort_example_matches_the_rfc(self):
        # Expected key order as published in RFC 8785 §3.2.3, not derived from our code.
        case = next(c for c in load("jcs.json")["cases"] if c["name"] == "rfc8785_3.2.3_key_sort")
        keys = list(json.loads(case["canonical"]))
        self.assertEqual(keys, ["\r", "1", "\u0080", "ö", "€", "\U0001F600", "דּ"])

    def test_SH_08_utf16_order_differs_from_code_point_order(self):
        # U+FF61 < U+1F600 by code point, but its UTF-16 unit FF61 > D83D, so the emoji sorts first.
        case = next(c for c in load("jcs.json")["cases"] if c["name"] == "key_sort_is_utf16_not_codepoint")
        self.assertEqual(case["canonical"], '{"\U0001F600":2,"｡":1}')

    def test_SH_08_must_reject_cases_raise(self):
        cases = load("jcs.json")["must_reject"]
        self.assertGreaterEqual(len(cases), 7)
        for c in cases:
            with self.assertRaises(ValueError, msg=c["name"]):
                rv.jcs(rv.parse(c["input"]))


class Chain(unittest.TestCase):
    def setUp(self):
        self.vec = load("chain.json")
        self.receipts = self.vec["receipts"]

    def test_SH_08_chain_hashes_and_links(self):
        self.assertEqual(len(self.receipts), 5)
        prev = "GENESIS"
        for i, entry in enumerate(self.receipts):
            r = entry["receipt"]
            self.assertEqual(r["previous_receipt_hash"], prev, i)
            self.assertEqual(rv.jcs(rv.hashed_view(r)), entry["canonical"], i)
            self.assertEqual(rv.sha256(entry["canonical"]), r["receipt_hash"], i)
            prev = r["receipt_hash"]
        # Without an ADR-018 checkpoint even an intact chain can't rule out a dropped tail.
        self.assertEqual(rv.verify_chain([e["receipt"] for e in self.receipts]),
                         {"ok": True, "limitation": "undetectable_without_checkpoint"})

    def test_SH_08_chain_has_deny(self):
        decisions = [e["receipt"]["decision"] for e in self.receipts]
        self.assertIn("DENY", decisions)
        self.assertEqual(decisions[0], "ALLOW")
        self.assertIn("EXECUTED", decisions)

    def test_SH_08_hash_view_follows_schema_annotation(self):
        exclude = json.loads(SCHEMA.read_text())["x-receipt-hash"]["exclude"]
        self.assertEqual(sorted(exclude), sorted(rv.EXCLUDE))
        self.assertEqual(self.vec["x-receipt-hash"]["exclude"], exclude)
        signed = dict(self.receipts[0]["receipt"], signature="x", signature_key_id="k")
        self.assertEqual(rv.hashed_view(signed), rv.hashed_view(self.receipts[0]["receipt"]))

    # Written by hand, not derived from verify_chain, so the vectors can't confirm themselves.
    EXPECTED = {
        "edited_no_rehash": {"ok": False, "reason": "HASH_MISMATCH", "index": 2},
        "edited_rehashed": {"ok": False, "reason": "LINK_BROKEN", "index": 3},
        "removed": {"ok": False, "reason": "LINK_BROKEN", "index": 2},
        "swapped": {"ok": False, "reason": "LINK_BROKEN", "index": 1},
        "truncated_tail": {"ok": True, "limitation": "undetectable_without_checkpoint"},
        "empty_chain": {"ok": False, "reason": "MALFORMED", "index": 0},
        "malformed_entry": {"ok": False, "reason": "MALFORMED", "index": 1},
        "missing_receipt_hash": {"ok": False, "reason": "MALFORMED", "index": 2},
        "missing_previous_receipt_hash": {"ok": False, "reason": "MALFORMED", "index": 0},
    }

    def test_SH_08_tamper_cases_detected(self):
        tamper = self.vec["tamper"]
        self.assertEqual({t["name"] for t in tamper}, set(self.EXPECTED))
        for t in tamper:
            self.assertEqual(t["expect"], self.EXPECTED[t["name"]], t["name"])
            self.assertEqual(rv.verify_chain(t["receipts"]), t["expect"], t["name"])

    def test_SH_08_verdicts_are_a_closed_set(self):
        reasons = {t["expect"].get("reason") for t in self.vec["tamper"]} - {None}
        self.assertEqual(reasons, {"HASH_MISMATCH", "LINK_BROKEN", "MALFORMED"})
        for bad in ([], [1], [None], ["x"], [{"receipt_hash": 5, "previous_receipt_hash": "GENESIS"}]):
            verdict = rv.verify_chain(bad)
            self.assertFalse(verdict["ok"], bad)

    def test_SH_08_truncation_needs_checkpoint(self):
        t = next(t for t in self.vec["tamper"] if t["name"] == "truncated_tail")
        self.assertEqual(t["expect"], {"ok": True, "limitation": "undetectable_without_checkpoint"})

    def test_SH_08_detection_points_at_first_bad_receipt(self):
        by_name = {t["name"]: t["expect"] for t in self.vec["tamper"]}
        self.assertEqual(by_name["edited_no_rehash"], {"ok": False, "reason": "HASH_MISMATCH", "index": 2})
        self.assertEqual(by_name["edited_rehashed"], {"ok": False, "reason": "LINK_BROKEN", "index": 3})


@unittest.skipUnless(shutil.which("uv") or os.environ.get("CI"), "uv not installed")  # CI: fail, never skip
class SchemaAndGuard(unittest.TestCase):
    def test_SH_08_chain_receipts_schema_valid(self):
        code = (
            "import json,sys\n"
            "from pathlib import Path\n"
            "from jsonschema import Draft202012Validator\n"
            "from referencing import Registry, Resource\n"
            "root=Path(sys.argv[1]); docs=[json.loads(p.read_text()) for p in root.rglob('*.schema.json')]\n"
            "reg=Registry().with_resources((d['$id'],Resource.from_contents(d)) for d in docs)\n"
            "s=json.loads((root/'receipts/decision_receipt.schema.json').read_text())\n"
            "v=json.loads((root/'test-vectors/receipts/chain.json').read_text())\n"
            "bad=[(i,e.message) for i,x in enumerate(v['receipts']) for e in Draft202012Validator(s,registry=reg).iter_errors(x['receipt'])]\n"
            "print(bad); sys.exit(1 if bad else 0)\n")
        r = subprocess.run(UV + ["-c", code, str(ROOT / "packages/contracts")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_SH_08_x_receipt_hash_guard(self):
        base = json.loads(SCHEMA.read_text())
        for bad in ({"exclude": ["signature"]},                      # receipt_hash must be excluded
                    {"exclude": ["receipt_hash", "ghost"]},          # unknown property
                    {"exclude": ["receipt_hash", "action_digest"]},  # required field dropped from the hash
                    {"exclude": ["receipt_hash", "error_code"]},     # optional, but a DENY's reason must be hashed
                    {"exclude": ["receipt_hash", "ledger_transaction_id"]}):
            root = Path(tempfile.mkdtemp())
            self.addCleanup(shutil.rmtree, root)
            shutil.copytree(ROOT / "packages/contracts", root, dirs_exist_ok=True)
            doc = dict(base, **{"x-receipt-hash": bad})
            (root / "receipts/decision_receipt.schema.json").write_text(json.dumps(doc))
            r = subprocess.run(UV + [str(ROOT / "scripts/contracts_check.py"), "--root", str(root)],
                               capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0, bad)
            self.assertIn("x-receipt-hash", r.stdout + r.stderr, bad)


if __name__ == "__main__":
    unittest.main()
