"""OM-01 CI hygiene (§19): pinned third-party actions, least privilege, pinned pre-commit hooks.
Stdlib only, like the kit: python3 -m unittest discover -s tests/kit"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = sorted((ROOT / ".github/workflows").glob("*.yml"))


class Workflows(unittest.TestCase):
    def test_OM_01_third_party_actions_sha_pinned(self):
        for wf in WORKFLOWS:
            for ref in re.findall(r"uses:\s*([^\s#]+)", wf.read_text()):
                if ref.startswith(("actions/", "./")):
                    continue
                self.assertRegex(ref, r"@[0-9a-f]{40}$", f"{wf.name}: {ref}")

    def test_OM_01_workflows_least_privilege(self):
        for wf in WORKFLOWS:
            self.assertRegex(wf.read_text(), r"(?m)^permissions:", wf.name)

    def test_OM_01_ci_has_the_required_jobs(self):
        text = (ROOT / ".github/workflows/ci.yml").read_text()
        for job in ("changes", "lint", "java", "stack"):
            self.assertRegex(text, rf"(?m)^  {job}:\s*$", job)
        self.assertIn("scripts/ci_changes.py", text)
        self.assertIn("gradle/actions/wrapper-validation@", text)
        self.assertIn("CI: \"1\"", text.replace("'", '"'))  # db-role suite must fail, not skip

    def test_OM_01_required_checks_include_new_jobs(self):
        settings = json.loads((ROOT / ".github/settings.json").read_text())
        main = next(r for r in settings["rulesets"] if r["name"] == "main")
        rule = next(r for r in main["rules"] if r["type"] == "required_status_checks")
        contexts = {c["context"] for c in rule["parameters"]["required_status_checks"]}
        self.assertEqual(contexts, {"kit", "changes", "lint", "java", "stack"})


class GateFailsClosed(unittest.TestCase):
    def test_OM_01_gating_job_is_required(self):
        # If `changes` fails, gated jobs are skipped and skipped == success; so `changes` itself must be required.
        text = (ROOT / ".github/workflows/ci.yml").read_text()
        gates = set(re.findall(r"(?m)^    needs: ([\w-]+)\s*$", text))
        settings = json.loads((ROOT / ".github/settings.json").read_text())
        main = next(r for r in settings["rulesets"] if r["name"] == "main")
        rule = next(r for r in main["rules"] if r["type"] == "required_status_checks")
        contexts = {c["context"] for c in rule["parameters"]["required_status_checks"]}
        self.assertTrue(gates)
        self.assertLessEqual(gates, contexts)


class SecretScan(unittest.TestCase):
    def test_OM_01_ci_scans_full_history_for_secrets(self):
        # The pre-commit gitleaks hook runs `--staged`: in CI (`--all-files`, nothing staged) it scans nothing.
        # So the lint job must also run a pinned, checksum-verified gitleaks over the whole history.
        text = (ROOT / ".github/workflows/ci.yml").read_text()
        lint = text.split("\n  lint:\n", 1)[1].split("\n  java:\n", 1)[0]
        self.assertIn("fetch-depth: 0", lint)
        self.assertRegex(lint, r"GITLEAKS_SHA256: [0-9a-f]{64}")
        self.assertIn("sha256sum -c", lint)
        self.assertRegex(lint, r"gitleaks git --redact[^\n]*--config \.gitleaks\.toml")


class DependabotPins(unittest.TestCase):
    def test_OM_01_pinned_majors_are_ignored_in_config(self):
        # Decided pins (OM-01 card + D3; declined majors on #19-#24) live in the repo, not only in Dependabot state.
        text = (ROOT / ".github/dependabot.yml").read_text()
        for dep in ("org.springframework.boot*", "gradle-wrapper", "eclipse-temurin", "postgres", "redis"):
            block = re.search(rf'dependency-name: "{re.escape(dep)}"\n\s*update-types: \["version-update:semver-major"\]', text)
            self.assertIsNotNone(block, dep)


class PreCommit(unittest.TestCase):
    def test_OM_01_precommit_hooks_pinned(self):
        text = (ROOT / ".pre-commit-config.yaml").read_text()
        revs = re.findall(r"rev:\s*(\S+)", text)
        self.assertTrue(revs)
        for rev in revs:
            self.assertRegex(rev, r"^v\d+\.\d+\.\d+$|^[0-9a-f]{40}$", rev)
        for hook in ("gitleaks", "end-of-file-fixer", "mixed-line-ending"):
            self.assertIn(f"id: {hook}", text)

    def test_OM_01_dependabot_docker_entries(self):
        text = (ROOT / ".github/dependabot.yml").read_text()
        for eco, d in (("docker", "/services/ledger"), ("docker", "/services/gateway"),
                       ("docker-compose", "/infra/compose")):
            self.assertRegex(text, rf'package-ecosystem:\s*{eco}\s*\n\s*directory:\s*"{d}"', (eco, d))


if __name__ == "__main__":
    unittest.main()
