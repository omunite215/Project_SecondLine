"""SH-02 errors.json (§8): exactly the spec's typed codes; one retryable; ORACLE_MISMATCH grader-only.
Stdlib only, like the kit: python3 -m unittest discover -s tests/kit"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC_CODES = {"PERMISSION_DENIED", "POLICY_DENIED", "REVIEW_REQUIRED", "APPROVAL_EXPIRED", "EVIDENCE_STALE",
              "STATE_CONFLICT", "IDEMPOTENCY_CONFLICT", "DOMAIN_INVALID", "INSUFFICIENT_EVIDENCE", "RUN_HALTED",
              "RETRYABLE_UNAVAILABLE", "ORACLE_MISMATCH"}


class Errors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads((ROOT / "packages/contracts/errors.json").read_text())
        cls.by_code = {e["code"]: e for e in cls.doc["errors"]}

    def test_SH_02_error_codes_exactly_spec(self):
        self.assertEqual(set(self.by_code), SPEC_CODES)
        self.assertEqual(len(self.doc["errors"]), len(SPEC_CODES), "duplicate code")

    def test_SH_02_only_unavailable_is_retryable(self):
        self.assertEqual({c for c, e in self.by_code.items() if e["retryable"]}, {"RETRYABLE_UNAVAILABLE"})

    def test_SH_02_oracle_mismatch_grader_only(self):
        self.assertEqual({c for c, e in self.by_code.items() if e["grader_only"]}, {"ORACLE_MISMATCH"})
        self.assertIsNone(self.by_code["ORACLE_MISMATCH"]["http_status"])

    def test_SH_02_http_statuses(self):
        expected = {"PERMISSION_DENIED": 403, "POLICY_DENIED": 403, "REVIEW_REQUIRED": 202, "APPROVAL_EXPIRED": 409,
                    "EVIDENCE_STALE": 409, "STATE_CONFLICT": 409, "IDEMPOTENCY_CONFLICT": 409, "DOMAIN_INVALID": 422,
                    "INSUFFICIENT_EVIDENCE": 422, "RUN_HALTED": 423, "RETRYABLE_UNAVAILABLE": 503}
        self.assertEqual({c: e["http_status"] for c, e in self.by_code.items() if c != "ORACLE_MISMATCH"}, expected)


if __name__ == "__main__":
    unittest.main()
