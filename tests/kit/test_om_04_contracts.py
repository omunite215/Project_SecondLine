"""OM-04 contracts 1.2.0 (§5 §9 §10 §12, ADR-015, REQ-001 REQ-002 REQ-011, T-EVAL-03): the ledger read/admin
paths exist and return the tool shapes, trades name a counterparty, settlement status keeps the evidence's
vocabulary, and the state hash excludes the per-run ns. Stdlib only, like the kit."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
C = ROOT / "packages/contracts"
NS = "/internal/v1/ns/{ns}"
# path → the §10 read tool whose output it returns
READS = {f"{NS}/breaks": "list_breaks",
         f"{NS}/breaks/{{break_id}}": "get_break",
         f"{NS}/trades/{{trade_id}}": "read_trade",
         f"{NS}/trades/{{trade_id}}/bookings": "read_bookings",
         f"{NS}/trades/{{trade_id}}/settlement": "read_settlement_status",
         f"{NS}/positions": "read_positions",
         f"{NS}/custodian-statement": "read_custodian_statement",
         f"{NS}/corporate-actions": "read_corporate_actions",
         f"{NS}/evidence/{{record_id}}": "read_evidence",
         f"{NS}/reference-data/{{record_id}}": "read_reference_data",
         f"{NS}/fx": "read_fx_snapshot"}
ADMIN = {"/admin/v1/ns": "post", "/admin/v1/ns/{ns}:load": "post", "/admin/v1/ns/{ns}/export": "get",
         "/admin/v1/ns/{ns}/state-hash": "get", "/admin/v1/ns/{ns}": "delete", "/admin/v1/runs": "post"}


def load(rel: str) -> dict:
    return json.loads((C / rel).read_text())


def blocks(yaml_text: str) -> dict[str, str]:
    """Top-level path → its YAML block (2-space path keys under `paths:`)."""
    out, cur = {}, None
    for line in yaml_text.splitlines():
        m = re.match(r"^  (/\S+):\s*$", line)
        if m:
            cur = m.group(1)
            out[cur] = ""
        elif re.match(r"^\S", line):
            cur = None
        elif cur:
            out[cur] += line + "\n"
    return out


class LedgerPaths(unittest.TestCase):
    def test_OM_04_every_read_tool_has_an_internal_get(self):
        paths = blocks((C / "openapi/ledger-internal.yaml").read_text())
        for path, tool in READS.items():
            self.assertIn(path, paths, path)
            body = paths[path]
            self.assertRegex(body, r"(?m)^    get:", path)
            self.assertIn(f"'../tools/{tool}.output.schema.json'", body, path)
            self.assertIn("'403'", body, f"{path}: unresolvable ids answer PERMISSION_DENIED")
            self.assertNotIn("run_id", body, f"{path}: the gateway maps run → ns; the ledger never sees run_id")

    def test_OM_04_as_of_version_only_where_the_tool_takes_it(self):
        paths = blocks((C / "openapi/ledger-internal.yaml").read_text())
        for path, tool in READS.items():
            takes = "as_of_version" in load(f"tools/{tool}.input.schema.json")["properties"]
            self.assertEqual("as_of_version" in paths[path], takes, path)

    def test_OM_04_admin_paths(self):
        paths = blocks((C / "openapi/ledger-admin.yaml").read_text())
        for path, method in ADMIN.items():
            self.assertIn(path, paths, path)
            self.assertRegex(paths[path], rf"(?m)^    {method}:", path)
        self.assertIn("'../scenario/world_bundle.schema.json'", paths["/admin/v1/ns/{ns}:load"])
        self.assertIn("'../scenario/ns_export.schema.json'", paths["/admin/v1/ns/{ns}/export"])

    def test_OM_04_load_errors_are_typed(self):
        # Rule 7: every rejection names its errors.json code; a different bundle in a loaded ns is IDEMPOTENCY_CONFLICT.
        load_block = blocks((C / "openapi/ledger-admin.yaml").read_text())["/admin/v1/ns/{ns}:load"]
        codes = {e["code"] for e in load("errors.json")["errors"]}
        for status, code in (("409", "IDEMPOTENCY_CONFLICT"), ("422", "DOMAIN_INVALID"), ("403", "PERMISSION_DENIED")):
            self.assertIn(code, codes)
            self.assertRegex(load_block, rf"'{status}': {{description: '{code}:", status)


class BundleCounterparties(unittest.TestCase):
    def test_OM_04_trades_name_a_counterparty(self):
        wb = load("scenario/world_bundle.schema.json")
        self.assertIn("counterparty_id", wb["$defs"]["trade"]["required"])
        for key in ("institutions", "counterparties"):
            self.assertIn(key, wb["required"], key)
        self.assertEqual(wb["$defs"]["counterparty"]["required"], ["counterparty_id", "institution_id"])

    def test_OM_04_minimal_bundle_counterparties_resolve(self):
        b = load("examples/scenario/world_bundle_minimal.json")
        inst = {i["institution_id"] for i in b["institutions"]}
        cps = {c["counterparty_id"] for c in b["counterparties"]}
        self.assertTrue(all(c["institution_id"] in inst for c in b["counterparties"]))
        self.assertTrue(all(t["counterparty_id"] in cps for t in b["trades"]))


class BookingShape(unittest.TestCase):
    ENTRY_TYPES = ["TRADE", "SETTLEMENT", "FEE", "FX_CONVERSION", "FX_REVALUATION", "CORPORATE_ACTION"]

    def test_OM_04_entries_carry_type_and_effective_date(self):
        # docs/domain.md: every entry has entry_type + effective_date; read_bookings returns both, and a
        # business date is never derived from a timestamp (rules/money.md).
        defs = load("scenario/world_bundle.schema.json")["$defs"]
        for d in ("journal_entry", "securities_movement"):
            self.assertIn("effective_date", defs[d]["required"], d)
            self.assertEqual(defs[d]["properties"]["entry_type"]["enum"], self.ENTRY_TYPES, d)
        # A closed set: a free-text type could carry a cause ("DUPLICATE_…").
        self.assertIn("entry_id", defs["securities_movement"]["required"])

    def test_OM_04_movements_group_into_balanced_entries(self):
        groups = {}
        for m in load("examples/scenario/world_bundle_minimal.json")["securities_movements"]:
            q = int(m["quantity"]) * (1 if m["side"] == "DR" else -1)
            groups[m["entry_id"]] = groups.get(m["entry_id"], 0) + q
        self.assertTrue(groups and all(v == 0 for v in groups.values()), groups)


class SettlementVocabulary(unittest.TestCase):
    def test_OM_04_settlement_status_keeps_evidence_enum(self):
        rec = load("scenario/world_bundle.schema.json")["$defs"]["evidence_record"]
        ev = next(r for r in rec["allOf"] if r["if"]["properties"]["kind"]["const"] == "SETTLEMENT_STATUS")
        evidence_enum = ev["then"]["properties"]["fields"]["properties"]["status"]["enum"]
        tool_enum = load("tools/read_settlement_status.output.schema.json")["properties"]["status"]["enum"]
        self.assertEqual(tool_enum, evidence_enum)


class StateHashScope(unittest.TestCase):
    def test_OM_04_T_EVAL_03_state_hash_excludes_ns(self):
        # ns is a fresh UUID per load (ADR-015), so a hash over it could never match across loads.
        desc = load("scenario/ns_export.schema.json")["description"]
        self.assertIn('without "ns"', desc)
        adr = (ROOT / "docs/adr/ADR-015-namespaces-truth-isolation.md").read_text()
        amendment = adr.split("## Amendment 1", 1)[1]  # an ACCEPTED ADR changes by amendment, not in place
        self.assertIn('without "ns"', amendment)


class MajorVersion(unittest.TestCase):
    def test_OM_04_breaking_change_is_major(self):
        # Required bundle fields + a renamed enum value break 1.x producers/consumers (.claude/rules/contracts.md).
        self.assertEqual((C / "VERSION").read_text().strip(), "2.0.0")
        self.assertEqual(load("scenario/world_bundle.schema.json")["properties"]["bundle_version"]["const"], "2.0")
        self.assertTrue(load("scenario/world_bundle.schema.json")["$id"].startswith(
            "https://secondline.invalid/contracts/2/"))


if __name__ == "__main__":
    unittest.main()
