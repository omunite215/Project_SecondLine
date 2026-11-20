"""SH-02 follow-ups from Kunal's #11/#13/#18 approvals (T-DOM-03, REQ-005, ADR-011, ADR-013, ADR-015):
retry-safe writes, token-bound run_id, opaque ids that can't name a split, a stricter truth guard, and the
decision register matching what both owners approved. Stdlib; contracts_check runs under `uv run --with`."""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
C = ROOT / "packages/contracts"
CMD = ["uv", "run", "-q", "--with", "jsonschema==4.26.0", "--with", "pyyaml==6.0.3", "python",
       str(ROOT / "scripts/contracts_check.py")]
SCHEMA = "https://json-schema.org/draft/2020-12/schema"
BASE = "https://secondline.invalid/contracts/1/"


def load(rel: str) -> dict:
    return json.loads((C / rel).read_text())


class RetrySafety(unittest.TestCase):
    def test_SH_02_clarification_requires_idempotency_key(self):
        # A retry must not send the counterparty message twice or burn C_msg twice (ADR-014).
        s = load("tools/request_counterparty_clarification.input.schema.json")
        self.assertIn("idempotency_key", s["required"])
        self.assertEqual(s["properties"]["idempotency_key"], {"$ref": "../common.schema.json#/$defs/uuid"})

    def test_SH_02_create_run_is_idempotent(self):
        text = (C / "openapi/gateway-tools.yaml").read_text()
        block = text.split("  /v1/runs:\n", 1)[1].split("\n  /", 1)[0]
        for needle in ("requestBody", "Idempotency-Key", "'201'", "'409'", "run_request.schema.json",
                       "run_token.schema.json"):
            self.assertIn(needle, block, needle)

    def test_SH_02_run_id_bound_to_token(self):
        text = (C / "openapi/gateway-tools.yaml").read_text()
        self.assertRegex(text, r"run_id[^\n]*token[^\n]*PERMISSION_DENIED")
        self.assertIn("run_id", (ROOT / "docs/adr/ADR-013-service-boundaries-mcp-adapter.md").read_text()
                      .split("## Verification")[-1])


class OpaqueIds(unittest.TestCase):
    def test_SH_02_opaque_id_cannot_name_a_split(self):
        d = load("common.schema.json")["$defs"]["opaque_id"]
        self.assertIn("not", d)
        self.assertTrue((C / "examples/invalid/opaque_id_names_split.json").exists())


class ErrorShapes(unittest.TestCase):
    def test_SH_02_error_response_matches_errors_json(self):
        runtime = [e["code"] for e in load("errors.json")["errors"] if not e["grader_only"]]
        self.assertEqual(load("error_response.schema.json")["properties"]["error_code"]["enum"], runtime)


@unittest.skipUnless(shutil.which("uv") or os.environ.get("CI"), "uv not installed")
class StricterGuard(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "VERSION").write_text("1.0.0\n")

    def tearDown(self):
        shutil.rmtree(self.root)

    def write(self, rel: str, doc):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(doc if isinstance(doc, str) else json.dumps(doc))

    def fails(self, needle: str):
        r = subprocess.run(CMD + ["--root", str(self.root)], capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(needle, r.stdout)

    def schema(self, **body) -> dict:
        return {"$schema": SCHEMA, "$id": BASE + "t.schema.json", "type": "object", **body}

    def test_SH_02_truth_names_in_other_keywords_rejected(self):
        for body in ({"patternProperties": {"^root_cause.*$": {"type": "string"}}},
                     {"dependentRequired": {"a": ["ground_truth"]}},
                     {"dependentSchemas": {"break_type": {"type": "object"}}},
                     {"$defs": {"hidden_label": {"type": "string"}}}):
            with self.subTest(body=list(body)):
                self.write("t.schema.json", self.schema(**body))
                self.fails("truth field")

    def test_SH_02_openapi_parameter_and_enum_names_checked(self):
        self.write("x.schema.json", {"$schema": SCHEMA, "$id": BASE + "x.schema.json", "type": "object"})
        for extra in ("      parameters: [{name: root_cause, in: query, schema: {type: string}}]\n",
                      "      parameters: [{name: q, in: query, schema: {enum: [OK, GROUND_TRUTH]}}]\n"):
            with self.subTest(extra=extra.strip()):
                self.write("openapi/a.yaml", "openapi: 3.1.0\ninfo: {title: t, version: 1.0.0}\npaths:\n  /x:\n"
                           "    get:\n" + extra + "      responses: {'200': {description: ok}}\n")
                self.fails("truth field")

    def test_SH_02_unresolvable_ref_keywords_rejected_in_visible_schemas(self):
        for body in ({"properties": {"a": {"$dynamicRef": "#meta"}}}, {"$anchor": "x"},
                     {"properties": {"a": {"$id": "https://elsewhere.invalid/x.json"}}}):
            with self.subTest(body=json.dumps(body)):
                self.write("t.schema.json", self.schema(**body))
                self.fails("not allowed in visible schemas")


class Records(unittest.TestCase):
    def test_SH_02_accepted_adrs_say_so(self):
        for adr, pr in (("ADR-013-service-boundaries-mcp-adapter.md", "#11"),
                        ("ADR-014-control-conditions.md", "#13"),
                        ("ADR-015-namespaces-truth-isolation.md", "#11"),
                        ("ADR-017-evidence-semantics.md", "#16")):
            status = (ROOT / "docs/adr" / adr).read_text().splitlines()[1]
            self.assertTrue(status.startswith("Status: ACCEPTED"), (adr, status))
            self.assertIn(pr, status, adr)

    def test_SH_02_register_rows_resolved(self):
        reg = (ROOT / "docs/adr/README.md").read_text()
        for n in ("013", "014", "015", "017"):
            self.assertRegex(reg, rf"(?m)^\| {n} \|[^\n]*\| ACCEPTED", n)
        for u in ("U3", "U4", "U5", "U10"):
            self.assertRegex(reg, rf"(?m)^\| {u} \|[^\n]*\| resolved", u)

    def test_SH_02_c_msg_unit_is_consistent(self):
        adr = (ROOT / "docs/adr/ADR-014-control-conditions.md").read_text()
        self.assertNotIn("`C_msg` = 1 per break", adr)
        self.assertIn("`C_msg` = number of breaks in the run", adr)

    def test_SH_02_setup_docs_copy_examples_from_docs_ai(self):
        for doc in ("docs/setup/KUNAL-macos.md", "docs/setup/OM-windows-wsl.md"):
            text = (ROOT / doc).read_text()
            self.assertRegex(text, r"cp \S*CLAUDE\.local\.md\.\w+\.example", doc)  # the step still exists
            for m in re.finditer(r"cp (\S*CLAUDE\.local\.md\.\w+\.example)", text):
                self.assertTrue(m.group(1).startswith("docs/ai/"), (doc, m.group(1)))


if __name__ == "__main__":
    unittest.main()
