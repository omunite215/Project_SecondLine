"""OM-25 repo settings as code (§19 §21): .github/settings.json vs live GitHub, fail closed.
Stdlib only, like the kit: python3 -m unittest discover -s tests/kit"""
import copy
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import gh_settings  # noqa: E402  # pyright: ignore[reportMissingImports]

REPO = "omunite215/Project_SecondLine"
SETTINGS = json.loads((ROOT / ".github/settings.json").read_text())
LIVE_API = json.loads((ROOT / "tests/kit/fixtures/om_25_live.json").read_text())  # raw `gh api` responses, 2026-10-28


class FakeGh:
    """Replays recorded `gh api` responses; records every call so tests can assert reads vs writes."""

    def __init__(self, responses: dict, fail: bool = False):
        self.responses, self.fail, self.calls = responses, fail, []

    def __call__(self, method: str, endpoint: str, _body: dict | None = None):
        self.calls.append((method, endpoint))
        if self.fail:
            raise gh_settings.SettingsError(f"gh api {endpoint}: HTTP 401")
        if method != "GET":
            return {}
        if endpoint not in self.responses:
            raise gh_settings.SettingsError(f"gh api {endpoint}: HTTP 404")
        return copy.deepcopy(self.responses[endpoint])


def run_cli(*args: str, gh: FakeGh) -> tuple[int, str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = gh_settings.main(list(args), gh=gh)
    return rc, buf.getvalue()


class Diff(unittest.TestCase):
    def test_OM_25_identical_settings_no_diff(self):
        self.assertEqual(gh_settings.diff(SETTINGS, copy.deepcopy(SETTINGS)), [])

    def test_OM_25_today_live_reports_six_gaps(self):
        live = gh_settings.fetch_live(REPO, SETTINGS, gh=FakeGh(LIVE_API))
        lines = gh_settings.diff(SETTINGS, live)
        self.assertEqual(len(lines), 6, lines)
        self.assertTrue(lines[0].startswith("labels.ai-review: missing"), lines)
        self.assertTrue(any(l.startswith("rulesets.main.bypass_actors: expected []") for l in lines), lines)
        self.assertTrue(any(l.startswith("rulesets.main.rules:") and '"require_last_push_approval": false' in l
                            for l in lines), lines)
        for name in ("merge-gate", "gate-tags-create", "gate-tags-immutable"):
            self.assertIn(f"rulesets.{name}: missing", lines)

    def test_OM_25_volatile_fields_ignored(self):
        bare = SETTINGS["rulesets"][0]
        raw = dict(copy.deepcopy(bare), id=1, node_id="x", created_at="t", updated_at="t", _links={},
                   source="r", source_type="Repository", current_user_can_bypass="never")
        self.assertEqual(gh_settings.normalize_ruleset(raw), gh_settings.normalize_ruleset(bare))

    def test_OM_25_rule_order_ignored(self):
        live = copy.deepcopy(SETTINGS)
        live["rulesets"][0]["rules"].reverse()
        live["rulesets"] = [gh_settings.normalize_ruleset(r) for r in live["rulesets"]]
        self.assertEqual(gh_settings.diff(SETTINGS, live), [])

    def test_OM_25_extra_live_ruleset_reported(self):
        live = copy.deepcopy(SETTINGS)
        live["rulesets"].append(dict(copy.deepcopy(SETTINGS["rulesets"][1]), name="foo"))
        self.assertIn("rulesets.foo: not in settings.json", gh_settings.diff(SETTINGS, live))

    def test_OM_25_extra_collaborator_reported(self):
        live = copy.deepcopy(SETTINGS)
        live["collaborators"]["mallory"] = "admin"
        self.assertIn("collaborators.mallory: not in settings.json", gh_settings.diff(SETTINGS, live))

    def test_OM_25_extra_github_default_labels_are_fine(self):
        live = copy.deepcopy(SETTINGS)
        live["labels"] = ["bug", "ai-review", "dependencies"]
        self.assertEqual(gh_settings.diff(SETTINGS, live), [])


class FailClosed(unittest.TestCase):
    def test_OM_25_missing_bypass_field_fails_closed(self):
        raw = copy.deepcopy(SETTINGS["rulesets"][0])
        del raw["bypass_actors"]
        with self.assertRaisesRegex(gh_settings.SettingsError, "admin view required"):
            gh_settings.normalize_ruleset(raw)
        api = copy.deepcopy(LIVE_API)
        del api[f"repos/{REPO}/rulesets/25804326"]["bypass_actors"]  # what a non-admin (Kunal) is served
        rc, out = run_cli("check", gh=FakeGh(api))
        self.assertEqual(rc, 1)
        self.assertIn("admin view required", out)
        self.assertNotIn("OK", out)

    def test_OM_25_gh_failure_fails_closed(self):
        rc, out = run_cli("check", gh=FakeGh(LIVE_API, fail=True))
        self.assertEqual(rc, 1)
        self.assertNotIn("OK", out)

    def test_OM_25_check_ok_when_live_matches(self):
        gh = FakeGh(LIVE_API)
        live = gh_settings.fetch_live(REPO, SETTINGS, gh=gh)
        self.assertNotEqual(gh_settings.diff(SETTINGS, live), [])  # sanity: today is not OK
        rc, out = run_cli("check", gh=FakeGh(self._api_matching_settings()))
        self.assertEqual((rc, out.strip()), (0, "OK"))

    @staticmethod
    def _api_matching_settings() -> dict:
        api = copy.deepcopy(LIVE_API)
        R = f"repos/{REPO}"
        api[f"{R}/labels?per_page=100"].append({"name": "ai-review"})
        api[f"{R}/rulesets"] = []
        for i, rs in enumerate(SETTINGS["rulesets"], start=1):
            api[f"{R}/rulesets"].append({"id": i, "name": rs["name"]})
            api[f"{R}/rulesets/{i}"] = dict(copy.deepcopy(rs), id=i, node_id="n", _links={})
        return api


class Apply(unittest.TestCase):
    def test_OM_25_apply_without_yes_only_reads(self):
        gh = FakeGh(LIVE_API)
        rc, out = run_cli("apply", gh=gh)
        self.assertEqual(rc, 0)
        self.assertTrue(gh.calls and all(m == "GET" for m, _ in gh.calls), gh.calls)
        self.assertIn("--yes", out)

    def test_OM_25_apply_yes_creates_gate_before_dropping_bypass(self):
        gh = FakeGh(LIVE_API)
        rc, _ = run_cli("apply", "--yes", gh=gh)
        self.assertEqual(rc, 0)
        writes = [(m, e) for m, e in gh.calls if m != "GET"]
        R = f"repos/{REPO}"
        self.assertEqual(writes, [("POST", f"{R}/rulesets")] * 3 + [("POST", f"{R}/labels"),
                                                                    ("PUT", f"{R}/rulesets/25804326")])

    def test_OM_25_apply_never_touches_people_or_secrets(self):
        gh = FakeGh(LIVE_API)
        run_cli("apply", "--yes", gh=gh)
        for _, endpoint in gh.calls:
            self.assertNotRegex(endpoint, r"collaborators/|secrets/|environments/[^/]+$")


if __name__ == "__main__":
    unittest.main()
