#!/usr/bin/env python3
"""GitHub repo settings as code for Second-Line (OM-25, stdlib only).

.github/settings.json is the source of truth for merge options, collaborators, labels, the claude-review
environment and every ruleset. Uses the human's own `gh` session; never reads tokens (secret NAMES only).

  check [--repo OWNER/NAME]         Diff live settings against settings.json. Prints OK or one line per gap.
                                    Exit 1 on any gap, any gh error, or a non-admin view (fail closed).
  apply [--repo OWNER/NAME] [--yes] Without --yes: print the writes it would make (GETs only).
                                    With --yes: create missing rulesets, then labels, then update differing
                                    rulesets (new restrictions land before old bypasses are removed).
                                    Collaborators, environments and secrets are printed as manual steps.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / ".github/settings.json"
REPO = "omunite215/Project_SecondLine"
RULESET_KEYS = ("name", "target", "enforcement", "conditions", "bypass_actors", "rules")

Gh = Callable[..., Any]  # gh(method, endpoint, body=None) -> parsed JSON


class SettingsError(Exception):
    pass


def run_gh(method: str, endpoint: str, body: dict | None = None) -> Any:
    cmd = ["gh", "api", "-X", method, endpoint] + (["--input", "-"] if body is not None else [])
    try:
        r = subprocess.run(cmd, input=json.dumps(body) if body is not None else None,
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise SettingsError(f"gh api {endpoint}: {e}") from e
    if r.returncode != 0:
        raise SettingsError(f"gh api {method} {endpoint}: {(r.stderr or r.stdout).strip()[:300]}")
    try:
        return json.loads(r.stdout) if r.stdout.strip() else {}
    except json.JSONDecodeError as e:
        raise SettingsError(f"gh api {endpoint}: unparsable response") from e


def normalize_ruleset(raw: dict) -> dict:
    """Comparable form: only the keys settings.json declares, rules sorted, null parameters dropped."""
    if "bypass_actors" not in raw:
        raise SettingsError(f"ruleset {raw.get('name')!r}: admin view required: bypass_actors missing "
                            "(run as a repo admin)")
    missing = [k for k in RULESET_KEYS if k not in raw]
    if missing:
        raise SettingsError(f"ruleset {raw.get('name')!r}: response lacks {missing}")
    rules = [{k: v for k, v in r.items() if not (k == "parameters" and v is None)} for r in raw["rules"]]
    out = {k: raw[k] for k in RULESET_KEYS}
    out["rules"] = sorted(rules, key=lambda r: r["type"])
    out["bypass_actors"] = sorted(raw["bypass_actors"], key=lambda a: json.dumps(a, sort_keys=True))
    return out


def fetch_live(repo: str, expected: dict, gh: Gh = run_gh) -> dict:
    """Live settings in settings.json's shape. Environments: only those settings.json names."""
    R = f"repos/{repo}"
    meta = gh("GET", R)
    live: dict = {
        "repo": {k: meta.get(k) for k in expected["repo"]},
        "collaborators": {c["login"]: c["role_name"] for c in gh("GET", f"{R}/collaborators")},
        "labels": [l["name"] for l in gh("GET", f"{R}/labels?per_page=100")],
        "environments": {},
        "repo_secrets": sorted(s["name"] for s in gh("GET", f"{R}/actions/secrets?per_page=100")["secrets"]),
        "rulesets": [],
        "_ids": {},
    }
    for env in expected["environments"]:
        pol = gh("GET", f"{R}/environments/{env}/deployment-branch-policies")
        sec = gh("GET", f"{R}/environments/{env}/secrets")
        live["environments"][env] = {"branch_policies": sorted(p["name"] for p in pol["branch_policies"]),
                                     "secrets": sorted(s["name"] for s in sec["secrets"])}
    for summary in gh("GET", f"{R}/rulesets"):
        rs = normalize_ruleset(gh("GET", f"{R}/rulesets/{summary['id']}"))
        live["rulesets"].append(rs)
        live["_ids"][rs["name"]] = summary["id"]
    return live


def _show(v: object) -> str:
    return json.dumps(v, sort_keys=True)


def diff(expected: dict, live: dict) -> list[str]:
    out: list[str] = []
    for k, v in expected["repo"].items():
        if live["repo"].get(k) != v:
            out.append(f"repo.{k}: expected {_show(v)} got {_show(live['repo'].get(k))}")
    for who, role in expected["collaborators"].items():
        if live["collaborators"].get(who) != role:
            out.append(f"collaborators.{who}: expected {role} got {live['collaborators'].get(who)}")
    out += [f"collaborators.{who}: not in settings.json" for who in live["collaborators"]
            if who not in expected["collaborators"]]
    out += [f"labels.{name}: missing" for name in expected["labels"] if name not in live["labels"]]
    for env, want in expected["environments"].items():
        got = live["environments"].get(env)
        if got is None:
            out.append(f"environments.{env}: missing")
            continue
        for k in ("branch_policies", "secrets"):
            if sorted(want[k]) != got[k]:
                out.append(f"environments.{env}.{k}: expected {_show(sorted(want[k]))} got {_show(got[k])}")
    env_secrets = {s for e in expected["environments"].values() for s in e["secrets"]}
    out += [f"repo_secrets.{s}: must be an environment secret only" for s in live["repo_secrets"] if s in env_secrets]
    live_rs = {r["name"]: r for r in live["rulesets"]}
    for want in expected["rulesets"]:
        got = live_rs.get(want["name"])
        if got is None:
            out.append(f"rulesets.{want['name']}: missing")
            continue
        want = normalize_ruleset(want)
        out += [f"rulesets.{want['name']}.{k}: expected {_show(want[k])} got {_show(got[k])}"
                for k in RULESET_KEYS if want[k] != got[k]]
    names = {r["name"] for r in expected["rulesets"]}
    out += [f"rulesets.{n}: not in settings.json" for n in live_rs if n not in names]
    return out


def plan_writes(repo: str, expected: dict, live: dict) -> list[tuple[str, str, dict | None]]:
    """Ordered writes: create rulesets, create labels, then update rulesets (removes old bypasses last)."""
    R = f"repos/{repo}"
    live_rs = {r["name"]: r for r in live["rulesets"]}
    creates = [("POST", f"{R}/rulesets", rs) for rs in expected["rulesets"] if rs["name"] not in live_rs]
    labels = [("POST", f"{R}/labels", {"name": n, "color": "5319e7"}) for n in expected["labels"]
              if n not in live["labels"]]
    updates = [("PUT", f"{R}/rulesets/{live['_ids'][rs['name']]}", rs) for rs in expected["rulesets"]
               if rs["name"] in live_rs and normalize_ruleset(rs) != live_rs[rs["name"]]]
    return creates + labels + updates


def main(argv: list[str], gh: Gh = run_gh) -> int:
    ap = argparse.ArgumentParser(prog="gh_settings.py", description="GitHub settings as code (OM-25)")
    ap.add_argument("cmd", choices=["check", "apply"])
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--yes", action="store_true", help="apply: actually write")
    a = ap.parse_args(argv)
    try:
        expected = json.loads(SETTINGS.read_text())
        live = fetch_live(a.repo, expected, gh=gh)
        gaps = diff(expected, live)
        if a.cmd == "check":
            print("OK" if not gaps else "\n".join(gaps))
            return 0 if not gaps else 1
        writes = plan_writes(a.repo, expected, live)
        manual = [g for g in gaps if g.startswith(("repo.", "collaborators.", "environments."))]
        for method, endpoint, body in writes:
            print(f"{'' if a.yes else 'would: '}gh api -X {method} {endpoint}"
                  + (f"  # {body.get('name')}" if body else ""))
            if a.yes:
                gh(method, endpoint, body)
        for g in manual:
            print(f"manual (Settings UI / gh, not automated): {g}")
        if not a.yes:
            print(f"{len(writes)} write(s) planned; rerun with --yes to apply, then `make gh-check`.")
        return 0
    except (SettingsError, OSError, KeyError, TypeError, json.JSONDecodeError) as e:
        print(f"gh_settings: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
