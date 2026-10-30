"""OM-02 §9 ADR-011: contracts_check guards the x-action-digest field list that the Java library and
the audit-verifier both read. Stdlib; the script itself runs under `uv run --with`."""
import hashlib
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


@unittest.skipUnless(shutil.which("uv") or os.environ.get("CI"), "uv not installed")  # CI: fail, never skip
class ActionDigestAnnotation(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "VERSION").write_text("1.0.0\n")

    def tearDown(self):
        shutil.rmtree(self.root)

    def run_check(self, annotation) -> subprocess.CompletedProcess:
        doc = {"$schema": SCHEMA, "$id": BASE + "action.schema.json", "type": "object",
               "additionalProperties": False, "required": ["a", "refs"],
               "properties": {"a": {"type": "string"}, "refs": {"type": "array"}, "note": {"type": "string"}},
               "x-action-digest": annotation}
        (self.root / "action.schema.json").write_text(json.dumps(doc))
        return subprocess.run(CMD + ["--root", str(self.root)], capture_output=True, text=True)

    def test_OM_02_valid_annotation_passes(self):
        r = self.run_check({"include": ["a", "refs"], "sort": {"refs": ["record_id", "version"]}})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_OM_02_unknown_field_rejected(self):
        r = self.run_check({"include": ["a", "ghost"], "sort": {}})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("x-action-digest", r.stdout + r.stderr)

    def test_OM_02_optional_field_rejected(self):
        # A digest over an optional field would differ between "absent" and "present"; the Java side throws.
        r = self.run_check({"include": ["a", "note"], "sort": {}})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("note", r.stdout + r.stderr)

    def test_OM_02_sort_outside_include_rejected(self):
        r = self.run_check({"include": ["a"], "sort": {"refs": ["record_id"]}})
        self.assertNotEqual(r.returncode, 0)

    def test_OM_02_duplicate_include_rejected(self):
        r = self.run_check({"include": ["a", "a"], "sort": {}})
        self.assertNotEqual(r.returncode, 0)


class CodegenJava(unittest.TestCase):
    """`make codegen` is deterministic and the committed Java enums are current (CI fails on a diff)."""
    GEN = ROOT / "scripts/codegen_java.py"
    COMMITTED = ROOT / "libs/contracts-java/src/generated/java"

    def generate(self) -> dict[str, bytes]:
        out = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, out)
        subprocess.run(["python3", str(self.GEN), "--out", str(out)], check=True, capture_output=True)
        return {p.relative_to(out).as_posix(): p.read_bytes() for p in sorted(out.rglob("*")) if p.is_file()}

    def test_OM_02_codegen_java_deterministic(self):
        first = self.generate()
        self.assertIn("com/secondline/contracts/generated/ErrorCode.java", first)
        self.assertEqual(first, self.generate())

    def test_OM_02_committed_java_is_current(self):
        committed = {p.relative_to(self.COMMITTED).as_posix(): p.read_bytes()
                     for p in sorted(self.COMMITTED.rglob("*")) if p.is_file()}
        self.assertEqual(self.generate(), committed, "run `make codegen-java` and commit the result")

    def test_OM_02_check_mode_flags_stale_output(self):
        out = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, out)
        subprocess.run(["python3", str(self.GEN), "--out", str(out)], check=True, capture_output=True)
        ok = subprocess.run(["python3", str(self.GEN), "--out", str(out), "--check"], capture_output=True)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        (out / "com/secondline/contracts/generated/ErrorCode.java").write_text("stale")
        stale = subprocess.run(["python3", str(self.GEN), "--out", str(out), "--check"], capture_output=True, text=True)
        self.assertNotEqual(stale.returncode, 0)
        self.assertIn("ErrorCode.java", stale.stdout + stale.stderr)


def jcs(o) -> str:
    """Independent stdlib RFC 8785 for integer-only documents (what the audit-verifier must reproduce)."""
    if isinstance(o, dict):
        keys = sorted(o, key=lambda k: k.encode("utf-16-be"))
        return "{" + ",".join(jcs(k) + ":" + jcs(o[k]) for k in keys) + "}"
    if isinstance(o, list):
        return "[" + ",".join(jcs(x) for x in o) + "]"
    if isinstance(o, bool) or o is None:
        return {True: "true", False: "false", None: "null"}[o]
    if isinstance(o, int):
        return str(o)
    if isinstance(o, str):
        return json.dumps(o, ensure_ascii=False)
    raise ValueError(f"not digestible: {o!r}")


class ActionDigestVectors(unittest.TestCase):
    """packages/contracts/test-vectors/action_digest.json is reproducible outside Java (ADR-011)."""
    CONTRACTS = ROOT / "packages/contracts"

    def test_OM_02_vectors_recompute_in_python(self):
        vec = json.loads((self.CONTRACTS / "test-vectors/action_digest.json").read_text())
        ann = json.loads((self.CONTRACTS / "actions/proposed_action.schema.json").read_text())["x-action-digest"]
        self.assertEqual(vec["x-action-digest"], ann, "vectors were made for a different field set")
        self.assertGreaterEqual(len(vec["cases"]), 3)
        for case in vec["cases"]:
            bound = {f: case["action"][f] for f in ann["include"]}
            bound["evidence_refs"] = sorted(bound["evidence_refs"],
                                            key=lambda r: (r["record_id"].encode("utf-16-be"), r["version"]))
            canonical = jcs(bound)
            self.assertEqual(canonical, case["canonical"], case["name"])
            self.assertEqual("sha256:" + hashlib.sha256(canonical.encode()).hexdigest(), case["action_digest"],
                             case["name"])

    def test_OM_02_vector_cases_differ(self):
        vec = json.loads((self.CONTRACTS / "test-vectors/action_digest.json").read_text())
        digests = [c["action_digest"] for c in vec["cases"]]
        self.assertEqual(len(digests), len(set(digests)))


if __name__ == "__main__":
    unittest.main()
