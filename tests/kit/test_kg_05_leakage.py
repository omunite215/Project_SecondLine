"""KG-05 (§5 §6 §15, REQ-006, T-DOM-03 T-SEC-06, SEC-11, RSK-11): `make leakage-check` fails on a planted canary,
truth field names or imports on agent-visible surfaces, non-opaque ids, and dev vs eval/blind overlap; the clean
tree passes. Stdlib only, like the kit: python3 -m unittest discover -s tests/kit"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "leakage.py"
CANARY = "SLCANARY-0123456789abcdef0123456789abcdef"


def run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), "--root", str(root)], capture_output=True, text=True)


def bundle(scenario_id: str = "scn_AbCd1234EfGh", trade: str = "trd_Zx81Kq0pLm2N", name: str = "Granite Foods plc") -> dict:
    return {"scenario_id": scenario_id, "as_of": "2026-03-02", "instruments": [{"isin": "QZ0000000012", "name": name}],
            "trades": [{"trade_id": trade, "quantity": "300", "price": "12.34560000"}],
            "evidence": [{"record_id": "evd_Qw12Er34Ty56", "fields": {"trade_ref": trade}, "text": f"BUY 300 {name}."}],
            "breaks": [{"break_id": "brk_Hj78Kl90Mn12", "trade_ids": [trade], "evidence_ids": ["evd_Qw12Er34Ty56"]}]}


def write(root: Path, rel: str, content: str | dict) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(content) if isinstance(content, dict) else content)
    return p


def clean_tree(root: Path) -> Path:
    write(root, "services/agent/src/sl_agent/graph.py", "def run(bundle):\n    return bundle['breaks']\n")
    write(root, "services/mcp-adapter/src/sl_mcp/tools.py", 'DESCRIPTION = "Read one evidence record."\n')
    write(root, "apps/console/src/page.tsx", "export const Page = () => null;\n")
    write(root, "data/generated/dev/truth/scn_AbCd1234EfGh.json", {"canary": CANARY, "breaks": [{"root_cause": "X"}]})
    write(root, "data/generated/dev/bundles/scn_AbCd1234EfGh.json", bundle())
    write(root, "data/generated/dev/manifests/scn_AbCd1234EfGh.json", {"scenario_id": "scn_AbCd1234EfGh"})
    write(root, "experiments/runs/r1/trace.jsonl", '{"tool": "read_evidence", "ok": true}\n')
    write(root, "packages/scenario-factory/src/sl_factory/truth.py", "root_cause = 'privileged code may say this'\n")
    write(root, "packages/evaluation/src/sl_eval/grader.py", "from sl_factory import generate\n")
    return root


class Leakage(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = clean_tree(Path(self._tmp.name))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def assertFails(self, rule: str) -> str:
        r = run(self.root)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(rule, r.stdout)
        self.assertNotIn(CANARY, r.stdout + r.stderr)  # findings never echo the secret
        return r.stdout

    def test_KG_05_clean_fixture_tree_passes(self) -> None:
        r = run(self.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_KG_05_clean_tree_passes(self) -> None:
        r = run(ROOT)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_KG_05_planted_canary_in_trace_fails(self) -> None:
        write(self.root, "experiments/runs/r1/trace.jsonl", json.dumps({"tool": "read_evidence", "text": CANARY}) + "\n")
        out = self.assertFails("canary")
        self.assertIn("experiments/runs/r1/trace.jsonl:1", out)

    def test_KG_05_generic_canary_prefix_in_console_fails(self) -> None:
        write(self.root, "apps/console/src/page.tsx", "const x = 'SLCANARY-ffffffffffffffff';\n")
        self.assertFails("canary")

    def test_KG_05_truth_field_name_on_mcp_surface_fails(self) -> None:
        write(self.root, "services/mcp-adapter/src/sl_mcp/tools.py", 'OUT = {"root_cause": None}\n')
        self.assertFails("truth-field")

    def test_KG_05_break_label_in_tool_response_fails(self) -> None:
        write(self.root, "experiments/runs/r1/responses.jsonl", '{"hint": "B7_SETTLEMENT_SHORTFALL"}\n')
        self.assertFails("truth-field")

    def test_KG_05_privileged_import_outside_privileged_packages_fails(self) -> None:
        write(self.root, "services/agent/src/sl_agent/cheat.py", "from sl_factory.generate import generate_scenario\n")
        self.assertFails("import")

    def test_KG_05_non_opaque_visible_id_fails(self) -> None:
        write(self.root, "data/generated/dev/bundles/scn_AbCd1234EfGh.json", bundle(trade="trd_evalAAAA1111"))
        self.assertFails("opaque-id")

    def test_KG_05_same_scenario_in_dev_and_eval_fails(self) -> None:
        write(self.root, "data/generated/eval/bundles/scn_Pq12Rs34Tu56.json", bundle("scn_Pq12Rs34Tu56", "trd_Ab12Cd34Ef56"))
        self.assertFails("split-overlap")

    def test_KG_05_distinct_eval_scenario_passes(self) -> None:
        write(self.root, "data/generated/eval/bundles/scn_Pq12Rs34Tu56.json",
              bundle("scn_Pq12Rs34Tu56", "trd_Ab12Cd34Ef56", name="Kestrel Optics AG"))
        r = run(self.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_KG_05_shared_template_id_across_splits_fails(self) -> None:
        write(self.root, "data/generated/dev/truth/explanations/scn_AbCd1234EfGh.json", {"template_id": "tpl_b2_7"})
        write(self.root, "data/generated/blind/truth/explanations/scn_Zz99Yy88Xx77.json", {"template_id": "tpl_b2_7"})
        self.assertFails("template-overlap")


if __name__ == "__main__":
    unittest.main()
