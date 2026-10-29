"""SH-02 OpenAPI skeletons (§8 §9): refs resolve, error responses carry errors.json codes, no truth fields.
Drives scripts/contracts_check.py on throwaway trees; stdlib only."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CMD = ["uv", "run", "-q", "--with", "jsonschema==4.26.0", "--with", "pyyaml==6.0.3", "python",
       str(ROOT / "scripts/contracts_check.py")]
OK_API = """openapi: 3.1.0
info: {title: t, version: 1.0.0}
paths:
  /v1/x:
    post:
      requestBody: {content: {application/json: {schema: {$ref: '../thing.schema.json'}}}}
      responses:
        '200': {description: ok, content: {application/json: {schema: {$ref: '../thing.schema.json'}}}}
        '409': {description: conflict, content: {application/json: {schema: {$ref: '../error_response.schema.json'}}}}
"""


@unittest.skipUnless(shutil.which("uv") or os.environ.get("CI"), "uv not installed")
class OpenApi(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "VERSION").write_text("1.0.0\n")
        for name in ("thing", "error_response"):
            (self.root / f"{name}.schema.json").write_text(json.dumps({
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": f"https://secondline.invalid/contracts/1/{name}.schema.json", "type": "object"}))
        (self.root / "openapi").mkdir()

    def tearDown(self):
        shutil.rmtree(self.root)

    def check(self, api: str) -> subprocess.CompletedProcess:
        (self.root / "openapi/a.yaml").write_text(api)
        return subprocess.run(CMD + ["--root", str(self.root)], capture_output=True, text=True, timeout=120)

    def test_SH_02_valid_openapi_passes(self):
        r = self.check(OK_API)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_SH_02_openapi_refs_resolve(self):
        r = self.check(OK_API.replace("../thing.schema.json'}}}}\n      responses", "../missing.schema.json'}}}}\n      responses"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("unresolved $ref", r.stdout)

    def test_SH_02_error_responses_use_error_codes(self):
        r = self.check(OK_API.replace("'../error_response.schema.json'", "'../thing.schema.json'"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("error response", r.stdout)

    def test_SH_02_no_truth_in_om_apis(self):
        r = self.check(OK_API + "components: {schemas: {X: {properties: {truth_ref: {type: string}}}}}\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("truth field", r.stdout)

    def test_SH_02_component_error_response_followed(self):
        api = OK_API.replace("'409': {description: conflict, content: {application/json: {schema: {$ref: '../error_response.schema.json'}}}}",
                             "'409': {$ref: '#/components/responses/Error'}")
        good = api + "components: {responses: {Error: {description: e, content: {application/json: {schema: {$ref: '../error_response.schema.json'}}}}}}\n"
        self.assertEqual(self.check(good).returncode, 0)
        bad = api + "components: {responses: {Error: {description: e, content: {application/json: {schema: {type: object}}}}}}\n"
        self.assertEqual(self.check(bad).returncode, 1)

    def test_SH_02_om_openapi_files_exist(self):
        for name in ("gateway-tools", "ledger-internal", "ledger-admin", "review"):
            self.assertTrue((ROOT / f"packages/contracts/openapi/{name}.yaml").exists(), name)


if __name__ == "__main__":
    unittest.main()
