"""SH-04 ADR-017 evidence semantics & detection gap (§5 §8 §25 U5, REQ-006, I5, T-DOM-04, F3).
OM-08 (pre-commit verifier) and KG-06 (grader) consume the B1–B8 table, so its shape is pinned here: one row per
break, a closed evidence vocabulary, typed errors only, and every break mapped to explicit detection-gap cases. Stdlib."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADR = ROOT / "docs/adr/ADR-017-evidence-semantics.md"
KINDS = {"INTERNAL_BOOKING", "BROKER_CONFIRM", "CUSTODIAN_STATEMENT", "NOSTRO_STATEMENT", "SETTLEMENT_STATUS",
         "CA_NOTICE", "SSI_RECORD", "FX_RATE_NOTICE", "COUNTERPARTY_MESSAGE"}
# §8 l.17 typed codes; ORACLE_MISMATCH is grader-only.
# TODO(SH-02): read packages/contracts/errors.json instead once it is on main.
ERRORS = {"PERMISSION_DENIED", "POLICY_DENIED", "REVIEW_REQUIRED", "APPROVAL_EXPIRED", "EVIDENCE_STALE",
          "STATE_CONFLICT", "IDEMPOTENCY_CONFLICT", "DOMAIN_INVALID", "INSUFFICIENT_EVIDENCE", "RUN_HALTED",
          "RETRYABLE_UNAVAILABLE", "ORACLE_MISMATCH"}
COLUMNS = ["break", "authoritative record", "agent must cite", "verifier catches synchronously (no truth)",
           "only the oracle catches"]


def text() -> str:
    return ADR.read_text()


def table() -> dict[str, list[str]]:
    rows = {}
    for line in text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("| B") and re.match(r"^B[1-8]\b", cells[0]):
            rows[cells[0].split()[0]] = cells
    return rows


class Adr017(unittest.TestCase):
    def test_SH_04_status_line(self):
        self.assertRegex(text(), r"(?m)^Status: (PROPOSED|ACCEPTED \(om ☑ kunal ☑, PR #\d+\))")

    def test_SH_04_U5_table_has_one_row_per_break_and_the_five_columns(self):
        self.assertIn("| " + " | ".join(COLUMNS) + " |", text())
        rows = table()
        self.assertEqual(sorted(rows), [f"B{i}" for i in range(1, 9)])
        for b, cells in rows.items():
            self.assertEqual(len(cells), 5, b)
            self.assertTrue(all(cells), b)

    def test_SH_04_evidence_vocabulary_is_closed(self):
        for b, cells in table().items():
            for col in (1, 2):
                used = set(re.findall(r"\b[A-Z][A-Z_]{4,}\b", cells[col])) - {"ESCALATE", "CLASSIFY"}
                self.assertTrue(used, f"{b}: {COLUMNS[col]} names no evidence kind")
                self.assertLessEqual(used, KINDS, f"{b}: {COLUMNS[col]}")

    def test_SH_04_counterparty_text_never_satisfies_required_evidence(self):
        # Untrusted text (§15 family 2) can be cited but never counts toward the minimum.
        for b, cells in table().items():
            self.assertNotIn("COUNTERPARTY_MESSAGE", cells[2], b)

    def test_SH_04_I5_error_codes_are_typed(self):
        error_shaped = ("_STALE", "_EVIDENCE", "_DENIED", "_INVALID", "_CONFLICT", "_EXPIRED", "_HALTED", "_UNAVAILABLE")
        codes = {c for c in re.findall(r"\b[A-Z]+(?:_[A-Z]+)+\b", text()) if c.endswith(error_shaped)}
        self.assertLessEqual(codes, ERRORS)
        for must in ("EVIDENCE_STALE", "INSUFFICIENT_EVIDENCE"):
            self.assertRegex(text(), rf"\*\*`?{must}`?\*\*", f"{must} needs a defined trigger")
        sync = " ".join(c[3] for c in table().values())
        self.assertNotIn("ORACLE_MISMATCH", sync)

    def test_SH_04_B7_denies_every_posting_like_domain_md(self):
        # domain.md B7: "none (no 1900, no 4100)", so no tolerance carve-out under a shortfall cause.
        self.assertNotIn("tolerance", table()["B7"][3])
        self.assertIn("any posting", table()["B7"][3])

    def test_SH_04_error_codes_match_their_triggers(self):
        # A non-designated FX source is a missing required record, not a stale one.
        self.assertRegex(table()["B4"][3], r"non-designated source[^;]*`INSUFFICIENT_EVIDENCE`")
        self.assertRegex(text(), r"designated source")

    def test_SH_04_contract_follow_up_is_labelled_planned(self):
        line = next(l for l in text().splitlines() if "SETTLEMENT_STATUS" in l and "enum" in l)
        self.assertIn("PLANNED", line)

    def test_SH_04_T_DOM_04_every_break_maps_to_defined_detection_gap_cases(self):
        defined = set(re.findall(r"(?m)^### (DG-\d+)\b", text()))
        self.assertGreaterEqual(len(defined), 4)
        used = set()
        for b, cells in table().items():
            ids = set(re.findall(r"DG-\d+", cells[4]))
            self.assertTrue(ids, f"{b}: oracle-only column must name detection-gap cases")
            used |= ids
        self.assertEqual(used, defined)

    def test_SH_04_readme_points_U5_at_adr_017(self):
        readme = (ROOT / "docs/adr/README.md").read_text()
        self.assertRegex(readme, r"\| 017 \| Evidence semantics & detection gap \| (PROPOSED|ACCEPTED)[^|]*\| U5 \| "
                                 r"ADR-017-evidence-semantics\.md \|")
        self.assertRegex(readme, r"\| U5 \| evidence semantics \| SH-04 → ADR-017 \| (proposed|resolved)")


if __name__ == "__main__":
    unittest.main()
