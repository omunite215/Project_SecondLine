"""SH-02 action / approval / receipt / event shapes (§8 §9 §12, C1–C9 in docs/plans/SH-02.md).
Behaviour on bad input is proven by examples/invalid/** (contracts_check requires each to FAIL its schema);
these tests pin which invalid cases must exist plus the field sets. Stdlib only."""
import hashlib
import json
import unittest
from pathlib import Path

C = Path(__file__).resolve().parents[2] / "packages/contracts"
ENVELOPE_FIELDS = {"event_id", "run_id", "scenario_id", "break_id", "actor_id", "action_id", "event_type",
                   "schema_version", "occurred_at", "committed_at", "aggregate_id", "aggregate_version",
                   "correlation_id", "causation_id", "policy_decision_id", "payload_hash", "evidence_hashes",
                   "transaction_id", "redaction_class"}
REASON_CODES = ["CUTOFF_TIMING", "PARTIAL_SETTLEMENT", "QUANTITY_MISMATCH", "ROUNDING_DIFFERENCE", "PRICE_MISMATCH",
                "FX_RATE_SOURCE", "MISSING_TRADE", "DUPLICATE_TRADE", "CORPORATE_ACTION_SPLIT",
                "CORPORATE_ACTION_OTHER", "CASH_SHORTFALL", "SSI_MISMATCH", "INSUFFICIENT_EVIDENCE",
                "OTHER_ESCALATION"]


def load(rel: str) -> dict:
    return json.loads((C / rel).read_text())


def jcs(value) -> bytes:
    """RFC 8785 subset sufficient for these examples (strings, integers, objects, arrays)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def action_digest(action: dict) -> str:
    body = {k: v for k, v in action.items() if k not in ("agent_explanation", "x-validates")}
    return "sha256:" + hashlib.sha256(jcs(body)).hexdigest()


class Shapes(unittest.TestCase):
    def test_SH_02_invalid_cases_exist(self):
        # Each is required to FAIL validation by contracts_check (Review Focus 1 + 3).
        for name in ("action_with_requires_approval", "action_with_budget", "action_with_approved_by",
                     "adjustment_amount_number", "adjustment_amount_exponent", "action_without_evidence",
                     "receipt_unknown_decision", "envelope_missing_payload_hash", "approval_float_state_version",
                     "classify_with_adjustment_parameters", "adjustment_negative_amount",
                     "adjustment_account_currency_mismatch", "booking_correction_negative_price",
                     "booking_correction_negative_quantity", "envelope_split_in_scenario_id"):
            self.assertTrue((C / f"examples/invalid/{name}.json").exists(), name)

    def test_SH_02_same_account_both_sides_is_a_validator_rule(self):
        # JSON Schema can't compare two fields; the shape documents it and OM-08's validator enforces it.
        d = load("actions/parameters/adjustment.schema.json")["description"]
        self.assertIn("debit_account != credit_account", d)

    def test_SH_02_proposed_action_fields(self):
        s = load("actions/proposed_action.schema.json")
        self.assertEqual(set(s["properties"]), {
            "action_id", "run_id", "break_id", "request_id", "tool_schema_version", "type", "reason_code",
            "parameters", "evidence_refs", "expected_state_version", "idempotency_key", "agent_explanation"})
        self.assertFalse(s["additionalProperties"])
        self.assertEqual(s["properties"]["type"]["enum"],
                         ["CLASSIFY", "BOOKING_CORRECTION", "CORPORATE_ACTION", "ADJUSTMENT", "ESCALATE"])
        self.assertEqual(s["properties"]["reason_code"]["enum"], REASON_CODES)

    def test_SH_02_envelope_fields_are_spec_fields(self):
        s = load("events/envelope.schema.json")
        self.assertEqual(set(s["properties"]), ENVELOPE_FIELDS)
        self.assertEqual(set(s["required"]), ENVELOPE_FIELDS - {"causation_id", "policy_decision_id",
                                                               "transaction_id", "action_id", "break_id"})

    def test_SH_02_receipt_decision_enum(self):
        s = load("receipts/decision_receipt.schema.json")
        self.assertEqual(s["properties"]["decision"]["enum"], ["ALLOW", "DENY", "REVIEW_REQUIRED", "EXECUTED"])
        self.assertEqual(s["properties"]["evidence_validation"]["enum"],
                         ["VALID", "EVIDENCE_STALE", "INSUFFICIENT_EVIDENCE", "INVALID"])
        codes = {e["code"] for e in load("errors.json")["errors"] if not e["grader_only"]}
        self.assertEqual(set(s["properties"]["error_code"]["enum"]), codes)  # never ORACLE_MISMATCH

    def test_SH_02_digest_ignores_explanation(self):
        a = load("examples/actions/proposed_action_adjustment.json")
        reworded = dict(a, agent_explanation="Different words, same action.")
        self.assertEqual(action_digest(a), action_digest(reworded))
        other = json.loads(json.dumps(a))
        other["parameters"]["amount"] = "0.02"
        self.assertNotEqual(action_digest(a), action_digest(other))


if __name__ == "__main__":
    unittest.main()
