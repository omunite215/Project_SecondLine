#!/usr/bin/env python3
"""Claude Code skills gate for Second-Line (stdlib only).

Required plugins/skills per person live in tooling/claude-skills.json. This script installs them, verifies
them, and backs the hooks that keep Claude from working until they're in place.

  install [--owner om|kg] [--card ID ...] [--with-binaries] [--update] [--yes] [--dry-run]
      Run in YOUR terminal (plugins run code with your privileges). Registers marketplaces, installs the
      owner's core plugins (+ task plugins for --card / doing cards), vendors pinned skills, then runs check.
  check [--owner om|kg] [--card ID ...] [--quiet]
      Verifies the claude CLI + version, plugins installed AND enabled, LSP binaries on PATH, vendored skills
      valid and at the locked commit, project skills/agents valid (`claude plugin validate`), gh logged in.
      Writes .claude/.skills-ok.json. Exit 1 when anything is missing (prints the exact fix commands).
  gate --session            SessionStart hook: one status line; re-checks when stale. Never fails.
  gate --edit               PreToolUse hook (Edit|Write): exit 2 blocks project edits until the gate is GREEN.
  gate --bash               PreToolUse hook (Bash): while RED only setup/read-only commands run.
  gate --next [ID]          /next-task: checks core + the card about to start. Never fails.
  list [--owner om|kg]      What you need and why.
  lint                      CI: manifest valid; every `- skills:` on the boards exists; project plugins enabled.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import board  # noqa: E402

MANIFEST = ROOT / "tooling/claude-skills.json"
LOCK = ROOT / "tooling/skills.lock.json"
STAMP = ROOT / ".claude/.skills-ok.json"
# Setup files stay editable while the gate is RED so Claude can help fix the setup itself.
EDIT_ALLOW = ("tooling/", ".claude/", "docs/setup/", "docs/team/SKILLS.md", "CLAUDE.local.md", "START_HERE.md")
# ...except the guardrails themselves: Claude must not loosen hooks, permissions or the manifest while RED.
EDIT_DENY = (".claude/settings.json", ".claude/settings.local.json", ".claude/hooks/",
             "tooling/claude-skills.json", "tooling/skills.lock.json")
ID_RE = re.compile(r"(OM|KG|SH)-\d{2}")
# Each `&&`/`||`/`;`/`|` segment must match whole-word. Refused outright: substitution, expansion ($ other than
# $CLAUDE_PROJECT_DIR, braces, backslashes), redirects other than 2>&1, background `&` and newlines.
SHELL_META = re.compile(r"[\n\r`<>\\${}]|(?<!&)&(?!&)")
PROJECT_DIR = re.compile(r"\$\{?CLAUDE_PROJECT_DIR\}?")
RISKY_FLAGS = {"--pre", "--hostname-bin"}  # rg options that run programs
# git accepts abbreviated long options (--out = --output), so git gets an allowlist instead of a denylist.
GIT_LONG = {"--oneline", "--stat", "--short", "--name-only", "--name-status", "--cached", "--staged", "--porcelain",
            "--graph", "--all", "--decorate", "--pretty", "--format", "--branch", "--list", "--show-current",
            "--patch", "--max-count", "--since", "--until", "--author", "--reverse", "--abbrev-commit"}
BASH_OK = re.compile(r"^\s*(make\s+(skills-[a-z-]+|kit-check|board-[a-z-]+|spec-check|ctx|help|hpc-check)(\s+(CARD=(OM|KG|SH)-\d{2}|BIN=1))*\s*$"
                     r'|python3\s+"?(\$\{?CLAUDE_PROJECT_DIR\}?/|' + re.escape(str(ROOT)) + r'/|\./)?scripts/(skills|board|ctx)\.py"?'
                     r"|claude\s+(plugin|--version|update)|(npm|pnpm)\s+(install|i)\s+-g|uv\s+tool\s+install|brew\s+install"
                     r"|sudo\s+apt(-get)?\s+install|gh\s+auth\s+(status|login)|git\s+(status|log|diff|branch|show)"
                     r"|(ls|cat|head|tail|wc|which|pwd|echo|rg|grep|command\s+-v))(?=\s|$)")
JDTLS = ('set -e; d="$HOME/.local/share/jdtls"; mkdir -p "$d" "$HOME/.local/bin"; '
         'curl -fsSL https://download.eclipse.org/jdtls/snapshots/jdt-language-server-latest.tar.gz | tar -xz -C "$d"; '
         'ln -sf "$d/bin/jdtls" "$HOME/.local/bin/jdtls"; echo "jdtls -> $HOME/.local/bin (keep it on PATH)"')
AUTO_BIN = {
    "pyright-langserver": [["npm", "install", "-g", "pyright"], ["uv", "tool", "install", "pyright"]],
    "typescript-language-server": [["npm", "install", "-g", "typescript-language-server", "typescript"]],
    "jdtls": [["brew", "install", "jdtls"], ["bash", "-c", JDTLS]],
}


def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def manifest_hash() -> str:
    return hashlib.sha256(MANIFEST.read_bytes()).hexdigest()[:16]


def pid(p: dict) -> str:
    return f"{p['name']}@{p['marketplace']}"


def entries(m: dict) -> dict:
    out = {p["name"]: {**p, "kind": "plugin"} for p in m.get("plugins", [])}
    out.update({v["name"]: {**v, "kind": "vendored"} for v in m.get("vendored_skills", [])})
    return out


def card_task_skills(m: dict, card, owner: str) -> list[str]:
    ents = entries(m)
    return [s for s in card.skills if s in ents and ents[s]["tier"] == "task" and owner in ents[s]["owners"]]


def needed(m: dict, owner: str, cards: list):
    wanted = set().union(*(set(c.skills) for c in cards)) if cards else set()

    def pick(e: dict) -> bool:
        return owner in e["owners"] and (e["tier"] == "core" or e["name"] in wanted)

    plugins = [p for p in m.get("plugins", []) if pick(p)]
    vend = [v for v in m.get("vendored_skills", []) if pick(v)]
    pnames = {p["name"] for p in plugins}
    bins = [b for b in m.get("binaries", []) if owner in b["owners"] and (not b.get("plugin") or b["plugin"] in pnames)]
    cmds = [c for c in m.get("commands", []) if owner in c["owners"]]
    return plugins, vend, bins, cmds


def run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as e:
        return subprocess.CompletedProcess(cmd, 127, "", str(e))
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", "timeout")


def version_tuple(s: str | None):
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", s or "")
    return tuple(int(x) for x in m.groups()) if m else None


def parse_plugin_list(text: str):
    """Tolerant parser for `claude plugin list --json` → {"name@marketplace": enabled}."""
    text = (text or "").strip()
    data = None
    for cand in (text, text.splitlines()[-1] if text else ""):
        try:
            data = json.loads(cand)
            break
        except Exception:
            continue
    if data is None:
        return None

    def walk(o):
        if isinstance(o, dict):
            yield o
            for v in o.values():
                yield from walk(v)
        elif isinstance(o, list):
            for v in o:
                yield from walk(v)

    found: dict[str, bool] = {}
    for d in walk(data):
        name = next((d[k] for k in ("id", "plugin", "pluginId", "name") if isinstance(d.get(k), str)), None)
        if not name:
            continue
        mkt = next((d[k] for k in ("marketplace", "marketplaceName") if isinstance(d.get(k), str)), None)
        key = name if ("@" in name or not mkt) else f"{name}@{mkt}"
        en = d.get("enabled")
        if not isinstance(en, bool):
            st = str(d.get("status", "")).lower()
            en = not any(w in st for w in ("disabled", "error", "fail", "missing", "not installed"))
        found[key] = found.get(key, False) or en
    return found


def list_installed():
    r = run(["claude", "plugin", "list", "--json"], 90)
    if r.returncode == 0:
        found = parse_plugin_list(r.stdout)
        if found is not None:
            return found, None
    r2 = run(["claude", "plugin", "list"], 90)
    if r2.returncode != 0:
        return None, (r.stderr or r2.stderr or "claude plugin list failed").strip()[:200]
    found = {}
    for line in r2.stdout.splitlines():
        mm = re.search(r"([\w.\-]+@[\w.\-]+)", line)
        if mm:
            found[mm.group(1)] = "disabled" not in line.lower()
    return found, None


def plugin_state(found: dict, p: dict):
    if pid(p) in found:
        return found[pid(p)]
    for k, v in found.items():
        if k.split("@")[0] == p["name"]:
            return v
    return None


def skill_meta(path: Path) -> dict:
    t = path.read_text(encoding="utf-8", errors="replace")
    m = re.match(r"^---\n(.*?)\n---", t, re.S)
    fm = m.group(1) if m else ""

    def get(k: str):
        mm = re.search(rf"^{k}:\s*(.+)$", fm, re.M)
        return mm.group(1).strip() if mm else None

    return {"name": get("name"), "description": get("description")}


def load_lock() -> dict:
    try:
        return json.loads(LOCK.read_text(encoding="utf-8")).get("skills", {})
    except Exception:
        return {}


def save_lock(lock: dict) -> None:
    LOCK.write_text(json.dumps({"note": "Pinned upstream commits for vendored skills. Re-pin with `make skills-update` and open a PR.",
                                "skills": dict(sorted(lock.items()))}, indent=2) + "\n", encoding="utf-8")


def select_cards(owner: str, card_ids) -> list:
    cards, _ = board.load()
    sel = [cards[i] for i in card_ids if i in cards]
    sel += [c for c in board.mine(cards, owner) if c.status == "doing" and c not in sel]
    return sel


def check(owner: str, card_ids=(), quiet: bool = False):
    m = load_manifest()
    sel = select_cards(owner, card_ids)
    plugins, vend, bins, cmds = needed(m, owner, sel)
    problems: list[str] = []
    fixes: list[str] = []

    def miss(problem: str, fix: str | None) -> None:
        problems.append(problem)
        if fix and fix not in fixes:
            fixes.append(fix)

    for b in bins:
        if not shutil.which(b["bin"]):
            miss(f"binary not on PATH: {b['bin']}", b.get("hint"))
    if shutil.which("claude"):
        v = version_tuple(run(["claude", "--version"], 30).stdout)
        need = version_tuple(m.get("min_claude_code", "0.0.0"))
        if not v or (need and v < need):
            miss(f"Claude Code {'.'.join(map(str, v)) if v else '?'} is older than {m.get('min_claude_code')}", "claude update")
        found, err = list_installed()
        if found is None:
            miss(f"cannot list plugins ({err})", "run `claude plugin list` in your terminal and update Claude Code")
        else:
            for p in plugins:
                st = plugin_state(found, p)
                if st is None:
                    mk = m["marketplaces"][p["marketplace"]]
                    pre = "" if mk.get("builtin") else f"claude plugin marketplace add {mk['source']} --scope {p['scope']} && "
                    miss(f"plugin not installed: {pid(p)}", f"{pre}claude plugin install {pid(p)} --scope {p['scope']}")
                elif not st:
                    miss(f"plugin disabled: {pid(p)}", f"claude plugin enable {pid(p)} --scope {p['scope']}")
        dirs = [".claude/skills", ".claude/agents"] + sorted({v["dest"] for v in vend if (ROOT / v["dest"]).exists()})
        for d in dirs:
            r = run(["claude", "plugin", "validate", str(ROOT / d)], 90)
            out = (r.stdout + r.stderr).strip()
            if r.returncode != 0 and not re.search(r"unknown (command|option)|usage:", out, re.I):
                first = out.splitlines()[0][:160] if out else "validate failed"
                miss(f"invalid skill/agent files in {d}: {first}", f"claude plugin validate {d}")
    lock = load_lock()
    for v in vend:
        dest = ROOT / v["dest"] / v["name"]
        if not (dest / "SKILL.md").exists() or not (dest / ".source.json").exists():
            miss(f"vendored skill missing: {v['name']} → {v['dest']}", "make skills-install")
            continue
        sm = skill_meta(dest / "SKILL.md")
        if not sm["name"] or not sm["description"]:
            miss(f"vendored skill without name/description frontmatter: {v['name']}", "make skills-install")
        src = json.loads((dest / ".source.json").read_text(encoding="utf-8"))
        locked = (lock.get(v["name"]) or {}).get("commit")
        if locked and src.get("commit") != locked:
            miss(f"vendored skill {v['name']} is not at the locked commit {locked[:10]}", "make skills-install")
    for c in cmds:
        if shutil.which(c["cmd"][0]) and run(c["cmd"], 30).returncode != 0:
            miss(f"check failed: {' '.join(c['cmd'])}", c.get("hint"))
    ok = not problems
    stamp = {"ok": ok, "owner": owner, "manifest": manifest_hash(), "checked_at": now().isoformat(timespec="seconds"),
             "cards_ok": [c.id for c in sel] if ok else [], "problems": problems}
    try:
        STAMP.parent.mkdir(parents=True, exist_ok=True)
        STAMP.write_text(json.dumps(stamp, indent=2), encoding="utf-8")
    except OSError:
        pass
    if not quiet:
        print(f"Skills gate for {board.NAMES[owner]}: " + ("GREEN ✓" if ok else f"RED ✗ ({len(problems)} problem(s))"))
        print("  plugins: " + (", ".join(pid(p) for p in plugins) or "none"))
        if vend:
            print("  vendored skills: " + ", ".join(v["name"] for v in vend))
        if sel:
            print("  cards checked: " + ", ".join(c.id for c in sel))
        for p in problems:
            print(f"  ✗ {p}")
        if fixes:
            print("Fix — run in YOUR terminal, then `make skills-check`:")
            for f in fixes:
                print(f"  {f}")
        else:
            print("If you just installed something, restart open Claude Code sessions (or run /reload-plugins).")
    return ok, problems, fixes


def stamp_status(owner: str):
    m = load_manifest()
    try:
        st = json.loads(STAMP.read_text(encoding="utf-8"))
    except Exception:
        return False, "skills have not been checked on this machine"
    if not st.get("ok"):
        return False, "last check failed: " + "; ".join(st.get("problems", [])[:3])
    if st.get("manifest") != manifest_hash():
        return False, "tooling/claude-skills.json changed since the last check"
    if st.get("owner") != owner:
        return False, f"the last check was for owner={st.get('owner')}"
    try:
        age_h = (now() - dt.datetime.fromisoformat(st["checked_at"])).total_seconds() / 3600
    except Exception:
        age_h = 1e9
    if age_h > m.get("stamp_max_age_hours", 48):
        return False, f"the last check is {age_h:.0f} h old"
    cards, _ = board.load()
    for c in board.mine(cards, owner):
        if c.status == "doing" and card_task_skills(m, c, owner) and c.id not in st.get("cards_ok", []):
            return False, f"task skills for {c.id} are not verified (make skills-check CARD={c.id})"
    return True, f"verified {age_h:.1f} h ago"


def gate_edit() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    ti = data.get("tool_input") or {}
    raw = str(ti.get("file_path") or ti.get("notebook_path") or "").replace("\\", "/")
    if not raw:
        return 0
    p = Path(raw)
    if not p.is_absolute():
        p = Path(data.get("cwd") or os.getcwd()) / p
    try:
        rel = p.resolve().relative_to(ROOT.resolve()).as_posix()
    except Exception:
        return 0  # outside this repository
    if rel == ".claude/.skills-ok.json":
        print("Blocked: the skills stamp is written only by `make skills-check`.", file=sys.stderr)
        return 2
    if rel.startswith(EDIT_ALLOW) and not rel.startswith(EDIT_DENY):
        return 0
    owner = board.detect_owner()
    if not owner:
        reason = "owner unknown — copy your CLAUDE.local.md example first"
    else:
        ok, reason = stamp_status(owner)
        if ok:
            return 0
    print(f"Blocked by the skills gate: {reason}. Project files stay locked until the required Claude plugins/skills "
          "are installed and verified. Ask the human to run in their own terminal: `make skills-install` then "
          "`make skills-check` (docs/team/SKILLS.md).", file=sys.stderr)
    return 2


def risky_args(segment: str) -> bool:
    try:
        toks = shlex.split(segment)
    except ValueError:  # unbalanced quotes: refuse rather than guess
        return True
    if toks[:1] == ["git"]:
        return any(t.startswith("--") and t.split("=", 1)[0] not in GIT_LONG for t in toks[2:])
    return any(t.split("=", 1)[0] in RISKY_FLAGS for t in toks)


def gate_bash() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    cmd = str((data.get("tool_input") or {}).get("command") or "")
    cmd = cmd.replace("2>&1", "")
    parts = [x for x in re.split(r"&&|\|\||;|\|", cmd) if x.strip()]
    if (parts and not SHELL_META.search(PROJECT_DIR.sub("", cmd)) and not any(map(risky_args, parts))
            and all(BASH_OK.match(x) for x in parts)):
        return 0
    owner = board.detect_owner()
    ok, reason = stamp_status(owner) if owner else (False, "owner unknown — copy your CLAUDE.local.md example first")
    if ok:
        return 0
    print(f"Blocked by the skills gate: {reason}. Until it's GREEN only setup/read-only commands run "
          "(make skills-*, claude plugin …, git status/log/diff, ls, rg …). Ask the human to run "
          "`make skills-install` then `make skills-check` in their own terminal.", file=sys.stderr)
    return 2


def gate_session() -> int:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print("[skills] CI review run — the local skills gate doesn't apply here; do not edit files.")
        return 0
    try:
        owner = board.detect_owner()
        if not owner:
            print("[skills] RED — owner unknown (create CLAUDE.local.md from your example). Project edits are locked.")
            return 0
        ok, why = stamp_status(owner)
        if not ok:
            ok, problems, _ = check(owner, quiet=True)
            why = "verified just now" if ok else "; ".join(problems[:3]) + (" …" if len(problems) > 3 else "")
        if ok:
            print(f"[skills] GREEN for {board.NAMES[owner]} ({why}). Use them as docs/team/SKILLS.md describes.")
        else:
            print(f"[skills] RED — {why}")
            print("[skills] Do NOT plan or edit code. Tell the human to run in their own terminal: "
                  "make skills-install && make skills-check — then restart this session.")
    except Exception as e:
        print(f"[skills] RED — gate error ({type(e).__name__}: {e}). Run `make skills-check` in a terminal.")
    return 0


def gate_next(args: list[str]) -> int:
    try:
        owner = board.detect_owner()
        if not owner:
            print("[skills] RED — owner unknown. STOP: create CLAUDE.local.md from your example first.")
            return 0
        cards, _ = board.load()
        ids = [a for a in args if ID_RE.fullmatch(a)]
        if not ids:
            cs = board.mine(cards, owner)
            doing = [c.id for c in cs if c.status == "doing"]
            ready = [c.id for c in cs if c.status == "todo" and board.dep_state(cards, c)[0]]
            ids = doing or ready[:1]
        ok, problems, fixes = check(owner, ids, quiet=True)
        if ok:
            print(f"[skills] GREEN — core set + task skills for {', '.join(ids) or 'no card'} verified.")
        else:
            print("[skills] RED — STOP. Do not plan or edit. Problems:")
            for p in problems:
                print(f"  - {p}")
            print("Ask the human to run in their own terminal:")
            for f in fixes or ["make skills-install && make skills-check"]:
                print(f"  {f}")
    except Exception as e:
        print(f"[skills] RED — gate error ({type(e).__name__}: {e}). STOP.")
    return 0


def sh(cmd: list[str], dry: bool) -> int:
    shown = cmd[:2] + ["<jdtls installer>"] if cmd[:2] == ["bash", "-c"] else cmd
    print("$ " + " ".join(shown))
    return 0 if dry else subprocess.run(cmd).returncode  # inherits stdio, so the human sees any prompt


def vendor(v: dict, lock: dict, update: bool) -> None:
    ref = v.get("ref", "main") if update else ((lock.get(v["name"]) or {}).get("commit") or v.get("ref", "main"))
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)

        def g(*a: str) -> subprocess.CompletedProcess:
            return subprocess.run(["git", "-C", tmp, *a], check=True, capture_output=True, text=True)

        g("init", "-q")
        g("remote", "add", "origin", f"https://github.com/{v['repo']}.git")
        g("fetch", "-q", "--depth", "1", "origin", ref)
        g("checkout", "-q", "FETCH_HEAD")
        commit = g("rev-parse", "HEAD").stdout.strip()
        src = next((sk.parent for sk in sorted(t.rglob("SKILL.md")) if ".git" not in sk.parts
                    and (sk.parent.name == v["name"] or skill_meta(sk)["name"] == v["name"])), None)
        if not src:
            raise RuntimeError(f"no SKILL.md named {v['name']} in {v['repo']}@{commit[:10]}")
        dest = ROOT / v["dest"] / v["name"]
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns(".git"))
        lic = next((p for p in sorted(t.glob("LICENSE*")) if p.is_file()), None)
        if lic:
            shutil.copy2(lic, dest / "LICENSE.upstream")
        rel = src.relative_to(t).as_posix()
        (dest / ".source.json").write_text(json.dumps({"repo": v["repo"], "commit": commit, "path": rel,
                                                       "license": lic.name if lic else None,
                                                       "fetched_at": now().isoformat(timespec="seconds")}, indent=2),
                                           encoding="utf-8")
        lock[v["name"]] = {"repo": v["repo"], "commit": commit, "path": rel}
        print(f"  vendored {v['name']} @ {commit[:10]} → {dest.relative_to(ROOT)}"
              + ("" if lic else "   (WARNING: no upstream LICENSE found — keep it local)"))


def install(owner: str, card_ids, with_bins: bool, update: bool, yes: bool, dry: bool) -> int:
    m = load_manifest()
    sel = select_cards(owner, card_ids)
    plugins, vend, bins, _ = needed(m, owner, sel)
    print(f"Installing for {board.NAMES[owner]}: " + ", ".join(pid(p) for p in plugins)
          + ((" + vendored " + ", ".join(v["name"] for v in vend)) if vend else ""))
    if with_bins:
        for b in bins:
            if shutil.which(b["bin"]):
                continue
            for cmd in AUTO_BIN.get(b["bin"], []):
                if shutil.which(cmd[0]) and (cmd[0] != "bash" or shutil.which("curl")):
                    if sh(cmd, dry) == 0:
                        break
            else:
                print(f"  install manually: {b['bin']} → {b.get('hint')}")
    if not shutil.which("claude"):
        print("Claude Code CLI not found. Install it: curl -fsSL https://claude.ai/install.sh | bash — then rerun.")
        return 1
    scopes_by_mkt: dict[str, set] = {}
    for p in plugins:
        scopes_by_mkt.setdefault(p["marketplace"], set()).add(p["scope"])
    for name, scopes in scopes_by_mkt.items():
        mk = m["marketplaces"][name]
        if mk.get("builtin"):
            if sh(["claude", "plugin", "marketplace", "update", name], dry) != 0:
                sh(["claude", "plugin", "marketplace", "add", mk["source"]], dry)
        else:
            sh(["claude", "plugin", "marketplace", "add", mk["source"], "--scope",
                "project" if scopes == {"project"} else "local"], dry)
    for p in plugins:
        sh(["claude", "plugin", "install", pid(p), "--scope", p["scope"]] + (["--yes"] if yes else []), dry)
    lock = load_lock()
    for v in vend:
        if dry:
            print(f"$ vendor {v['repo']}:{v['name']} → {v['dest']}")
            continue
        try:
            vendor(v, lock, update)
        except Exception as e:
            print(f"  vendoring {v['name']} failed: {e}")
    if vend and not dry:
        save_lock(lock)
    if dry:
        return 0
    print()
    ok, _, _ = check(owner, card_ids)
    return 0 if ok else 1


def cmd_list(owner: str) -> int:
    m = load_manifest()
    cards, _ = board.load()
    print(f"Claude plugins/skills for {board.NAMES[owner]} (manifest {manifest_hash()}):")
    for e in list(m.get("plugins", [])) + list(m.get("vendored_skills", [])):
        if owner not in e["owners"]:
            continue
        label = pid(e) if "marketplace" in e else f"{e['name']} (vendored from {e['repo']})"
        used = [c.id for c in cards.values() if e["name"] in c.skills]
        print(f"  [{e['tier']}] {label} — {e['why']}" + (f"  · cards: {', '.join(used)}" if used else ""))
    for b in m.get("binaries", []):
        if owner in b["owners"]:
            print(f"  [bin] {b['bin']}: {'ok' if shutil.which(b['bin']) else 'MISSING → ' + b.get('hint', '')}")
    return 0


def lint() -> int:
    errs: list[str] = []
    m = load_manifest()
    names = [p.get("name") for p in m.get("plugins", [])] + [v.get("name") for v in m.get("vendored_skills", [])]
    errs += [f"duplicate skill name: {n}" for n in sorted({n for n in names if names.count(n) > 1})]
    for p in m.get("plugins", []):
        errs += [f"plugin {p.get('name')}: missing '{k}'" for k in ("name", "marketplace", "owners", "tier", "scope", "why") if k not in p]
        if p.get("marketplace") not in m.get("marketplaces", {}):
            errs.append(f"plugin {p.get('name')}: unknown marketplace {p.get('marketplace')}")
        if p.get("tier") not in ("core", "task") or p.get("scope") not in ("user", "project", "local"):
            errs.append(f"plugin {p.get('name')}: tier must be core|task and scope user|project|local")
        if not set(p.get("owners", [])) <= {"om", "kg"}:
            errs.append(f"plugin {p.get('name')}: owners must be om/kg")
    for v in m.get("vendored_skills", []):
        errs += [f"vendored {v.get('name')}: missing '{k}'" for k in ("name", "repo", "dest", "owners", "tier", "why") if k not in v]
    pnames = {p["name"] for p in m.get("plugins", [])}
    errs += [f"binary {b['bin']}: unknown plugin {b['plugin']}" for b in m.get("binaries", []) if b.get("plugin") and b["plugin"] not in pnames]
    ents = entries(m)
    cards, _ = board.load()
    for c in cards.values():
        for s in c.skills:
            e = ents.get(s)
            if not e:
                errs.append(f"{c.id}: unknown skill '{s}' (add it to tooling/claude-skills.json)")
            elif not set(c.owners) & set(e["owners"]) or (c.id[:2] != "SH" and c.owners[0] not in e["owners"]):
                errs.append(f"{c.id}: skill '{s}' isn't provisioned for {'/'.join(c.owners)}")
    enabled = json.loads((ROOT / ".claude/settings.json").read_text(encoding="utf-8")).get("enabledPlugins", {})
    project = {pid(p) for p in m.get("plugins", []) if p.get("scope") == "project"}
    errs += [f".claude/settings.json enabledPlugins lacks project-scope plugin {x}" for x in sorted(project) if enabled.get(x) is not True]
    errs += [f".claude/settings.json enables {x}, which the manifest doesn't list as project-scope" for x in sorted(set(enabled) - project)]
    if errs:
        print("\n".join(errs))
        return 1
    print(f"skills manifest OK: {len(m.get('plugins', []))} plugins, {len(m.get('vendored_skills', []))} vendored skills, "
          f"{sum(len(c.skills) for c in cards.values())} card references")
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    cards_arg = [a for a in rest if ID_RE.fullmatch(a)]

    def owner():
        o = board.detect_owner(board.opt(rest, "--owner"))
        if not o:
            print("Owner unknown: copy CLAUDE.local.md.<om|kunal>.example to CLAUDE.local.md, or pass --owner om|kg.", file=sys.stderr)
        return o

    if cmd == "gate":
        if "--edit" in rest:
            return gate_edit()
        if "--bash" in rest:
            return gate_bash()
        if "--next" in rest:
            return gate_next(rest)
        return gate_session()
    if cmd == "lint":
        return lint()
    o = owner()
    if not o:
        return 1
    if cmd == "install":
        return install(o, cards_arg, "--with-binaries" in rest, "--update" in rest, "--yes" in rest, "--dry-run" in rest)
    if cmd == "check":
        return 0 if check(o, cards_arg, quiet="--quiet" in rest)[0] else 1
    if cmd == "list":
        return cmd_list(o)
    print(__doc__)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except BrokenPipeError:
        sys.exit(0)
