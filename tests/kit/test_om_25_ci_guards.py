"""OM-25 CI guards (§19 §21): pin the merge model in .github/settings.json and keep CI config consistent.
No network. Stdlib only, like the kit: python3 -m unittest discover -s tests/kit"""
import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SETTINGS = json.loads((ROOT / ".github/settings.json").read_text())
WORKFLOWS = ROOT / ".github/workflows"
ADMIN = {"actor_id": 5, "actor_type": "RepositoryRole"}


def ruleset(name: str) -> dict:
    return next(r for r in SETTINGS["rulesets"] if r["name"] == name)


def rule(rs: dict, rtype: str) -> dict:
    return next(r for r in rs["rules"] if r["type"] == rtype)


def top_block(text: str, key: str) -> list[str]:
    """Lines of a top-level YAML block (`key:` at column 0) up to the next top-level key."""
    lines, out, inside = text.splitlines(), [], False
    for line in lines:
        if re.match(rf"^{re.escape(key)}:", line):
            inside = True
            out.append(line)
            continue
        if inside and re.match(r"^\S", line):
            break
        if inside:
            out.append(line)
    return out


def triggers(text: str) -> set[str]:
    block = top_block(text, "on")
    inline = re.match(r"^on:\s*\[(.*)\]", block[0]) if block else None
    if inline:
        return {t.strip() for t in inline.group(1).split(",")}
    return {m.group(1) for l in block[1:] if (m := re.match(r"^  ([\w-]+):?\s*$", l))}


def job_ids(text: str) -> set[str]:
    return {m.group(1) for l in top_block(text, "jobs")[1:] if (m := re.match(r"^  ([\w-]+):\s*$", l))}


def tracked(name: str) -> list[Path]:
    out = subprocess.run(["git", "ls-files", f"*{name}", name], cwd=ROOT, capture_output=True, text=True,
                         check=True).stdout.split()
    return [ROOT / p for p in out if "node_modules/" not in p and Path(p).name == name]


class MergeModel(unittest.TestCase):
    def test_OM_25_main_ruleset_has_no_bypass(self):
        main = ruleset("main")
        self.assertEqual(main["bypass_actors"], [])
        self.assertEqual(main["conditions"]["ref_name"]["include"], ["~DEFAULT_BRANCH"])
        self.assertEqual(main["enforcement"], "active")
        pr = rule(main, "pull_request")["parameters"]
        self.assertGreaterEqual(pr["required_approving_review_count"], 1)
        for k in ("require_code_owner_review", "dismiss_stale_reviews_on_push", "required_review_thread_resolution"):
            self.assertIs(pr[k], True, k)
        self.assertEqual(pr["allowed_merge_methods"], ["squash"])
        checks = rule(main, "required_status_checks")["parameters"]
        self.assertIs(checks["strict_required_status_checks_policy"], True)
        self.assertTrue(checks["required_status_checks"])
        self.assertEqual({r["type"] for r in main["rules"]} >= {"deletion", "non_fast_forward"}, True)

    def test_OM_25_only_admin_can_merge(self):
        gate = ruleset("merge-gate")
        self.assertEqual(gate["enforcement"], "active")
        self.assertEqual(gate["conditions"]["ref_name"]["include"], ["~DEFAULT_BRANCH"])
        self.assertEqual(gate["rules"], [{"type": "update"}])
        self.assertEqual(gate["bypass_actors"], [dict(ADMIN, bypass_mode="pull_request")])

    def test_OM_25_gate_tags_immutable(self):
        imm, create = ruleset("gate-tags-immutable"), ruleset("gate-tags-create")
        for rs in (imm, create):
            self.assertEqual((rs["target"], rs["enforcement"]), ("tag", "active"))
            self.assertEqual(rs["conditions"]["ref_name"]["include"], ["refs/tags/m*"])
        self.assertEqual({r["type"] for r in imm["rules"]}, {"update", "deletion", "non_fast_forward"})
        self.assertEqual(imm["bypass_actors"], [])
        self.assertEqual(create["rules"], [{"type": "creation"}])
        self.assertEqual(create["bypass_actors"], [dict(ADMIN, bypass_mode="always")])

    def test_OM_25_no_ruleset_bypass_beyond_admin(self):
        for rs in SETTINGS["rulesets"]:
            for actor in rs["bypass_actors"]:
                self.assertEqual({k: actor[k] for k in ADMIN}, ADMIN, rs["name"])


class CiConsistency(unittest.TestCase):
    def test_OM_25_required_checks_are_pr_jobs(self):
        pr_jobs = set()
        for wf in WORKFLOWS.glob("*.yml"):
            text = wf.read_text()
            if "pull_request" in triggers(text):
                pr_jobs |= job_ids(text)
        self.assertIn("kit", pr_jobs)  # sanity: the parser sees today's only check
        contexts = [c["context"] for c in rule(ruleset("main"), "required_status_checks")["parameters"]
                    ["required_status_checks"]]
        for c in contexts:
            self.assertIn(c, pr_jobs, f"required check {c!r} has no pull_request job — every merge would block")

    def test_OM_25_ai_review_label_matches_workflow(self):
        self.assertIn("ai-review", SETTINGS["labels"])
        text = (WORKFLOWS / "claude-review.yml").read_text()
        self.assertEqual(triggers(text), {"pull_request_target"})
        self.assertIn("github.event.label.name == 'ai-review'", text)
        self.assertIn("github.event.sender.login == 'omunite215'", text)
        self.assertIn("environment: claude-review", text)
        self.assertNotRegex(text, r"^\s+ref:", "never check out the PR head under pull_request_target")

    def test_OM_25_dependabot_covers_build_files(self):
        text = (ROOT / ".github/dependabot.yml").read_text()
        entries = set(re.findall(r'package-ecosystem:\s*"?([\w-]+)"?\s*\n\s*directory:\s*"?([^"\n]+)"?', text))
        self.assertIn(("github-actions", "/"), entries)
        wanted = {"build.gradle.kts": {"gradle"}, "pyproject.toml": {"uv", "pip"}, "package.json": {"npm"}}
        for name, ecosystems in wanted.items():
            for f in tracked(name):
                rel = f.parent.relative_to(ROOT).as_posix()
                d = "/" if rel == "." else f"/{rel}"
                self.assertTrue(any((e, d) in entries for e in ecosystems),
                                f"{f.relative_to(ROOT)}: add a dependabot entry ({'|'.join(ecosystems)}, {d})")

    def test_OM_25_kit_runs_every_kit_test(self):
        mk = (ROOT / "Makefile").read_text()
        ci = (WORKFLOWS / "kit-checks.yml").read_text()
        self.assertNotIn("test_om_26_*", mk + ci)
        self.assertRegex(mk, r"-p 'test_\*\.py'")
        self.assertEqual(len(re.findall(r"-p 'test_\*\.py'", ci)), 2)


if __name__ == "__main__":
    unittest.main()
