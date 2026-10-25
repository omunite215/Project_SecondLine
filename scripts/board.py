#!/usr/bin/env python3
"""Second-Line task-board tool (stdlib only). Keeps Claude's context small: it prints exactly the
card(s) needed instead of Claude reading whole boards.

Boards: docs/team/OM.md, docs/team/KUNAL.md, docs/team/SHARED.md
Card format (one per task):
  ### OM-05 · Title
  - meta: P0 | M-2 | 4d | mcs | learn | deps: OM-02, SH-02 | status: todo
  - refs: §8 §10 | REQ-005 | T-SEC-01 | SEC-03 ...           (ranges like MET-01..12 allowed)
  - build: ...
  - done: ...
  - notes: ...            (optional)
  - evidence: ...         (written by `set --evidence`)
Shared cards use `om=1d kg=0.5d | driver: om` instead of a single estimate.

Commands:
  brief                           ≤3 lines for the SessionStart hook (never fails)
  next [ID ...] [--owner om|kg] [--n N]   doing card(s), else next unblocked card(s) (never fails)
  show ID ... | show --doing      print cards
  set ID STATUS [--evidence TXT]  STATUS: todo|doing|review|done|blocked|cut
  check                           validate boards + coverage of every spec ID (exit 1 on problems)
  trace [--write]                 coverage matrix -> docs/team/TRACEABILITY.md
  summary [--brief] [--write]     effort per person (total / P0 / MCS / remaining); --write updates PLAN.md block
Owner: --owner, else $SL_OWNER, else `owner:` line in CLAUDE.local.md.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEAM = ROOT / "docs/team"
BOARDS = {"OM": TEAM / "OM.md", "KG": TEAM / "KUNAL.md", "SH": TEAM / "SHARED.md"}
STATUSES = ["todo", "doing", "review", "done", "blocked", "cut"]
MILESTONES = [f"M-{i}" for i in range(6)]
PRIORITIES = ["P0", "P1", "P2"]
NAMES = {"om": "Om", "kg": "Kunal"}
HEAD_RE = re.compile(r"^### ((?:OM|KG|SH)-\d{2})\s*[·:\-–—]\s*(.+?)\s*$")
FIELD_RE = re.compile(r"^- (meta|refs|skills|build|done|notes|evidence):\s*(.*)$")


@dataclass
class Card:
    id: str
    title: str
    file: Path
    start: int  # line index of header
    end: int  # exclusive
    fields: dict = field(default_factory=dict)
    priority: str = ""
    milestone: str = ""
    est: dict = field(default_factory=dict)  # {"om": 1.0} / {"kg": 2.0} / both for SH
    mcs: dict = field(default_factory=dict)
    learn: bool = False
    driver: str = ""
    deps: list = field(default_factory=list)
    status: str = ""
    refs: set = field(default_factory=set)
    skills: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    @property
    def owners(self) -> list[str]:
        return {"OM": ["om"], "KG": ["kg"], "SH": ["om", "kg"]}[self.id[:2]]

    def text(self, lines: list[str]) -> str:
        return "".join(lines[self.start:self.end]).rstrip() + "\n"


def norm_owner(o: str | None) -> str | None:
    if not o:
        return None
    o = o.strip().lower()
    return {"om": "om", "o": "om", "kunal": "kg", "kg": "kg", "k": "kg"}.get(o)


def detect_owner(cli: str | None = None) -> str | None:
    if cli:
        return norm_owner(cli)
    env = norm_owner(os.environ.get("SL_OWNER"))
    if env:
        return env
    local = ROOT / "CLAUDE.local.md"
    if local.exists():
        m = re.search(r"^owner:\s*([A-Za-z]+)", local.read_text(encoding="utf-8"), re.M)
        if m:
            return norm_owner(m.group(1))
    return None


def expand(tok: str) -> list[str]:
    """MET-01..MET-12 | MET-01..12 | I1..I12 | T-DOM-01..05 -> explicit IDs."""
    tok = tok.strip(",;")
    m = re.fullmatch(r"([A-Za-z§\-]*?)(\d+)\.\.(?:[A-Za-z§\-]*?)(\d+)", tok)
    if not m:
        return [tok] if tok else []
    prefix, a, b = m.group(1), m.group(2), m.group(3)
    width = len(a) if a.startswith("0") else 0
    return [f"{prefix}{str(i).zfill(width)}" for i in range(int(a), int(b) + 1)]


def parse_est(val: str) -> float:
    m = re.fullmatch(r"(\d+(?:\.\d+)?)d", val.strip())
    if not m:
        raise ValueError(val)
    return float(m.group(1))


def parse_meta(c: Card, meta: str) -> None:
    for part in [p.strip() for p in meta.split("|")]:
        if not part:
            continue
        low = part.lower()
        if part in PRIORITIES:
            c.priority = part
        elif part in MILESTONES:
            c.milestone = part
        elif low.startswith("status:"):
            c.status = low.split(":", 1)[1].strip()
        elif low.startswith("deps:"):
            raw = part.split(":", 1)[1]
            c.deps = [d.strip() for d in raw.split(",") if re.fullmatch(r"(OM|KG|SH)-\d{2}", d.strip())]
        elif low.startswith("driver:"):
            c.driver = norm_owner(part.split(":", 1)[1]) or ""
        elif low == "learn":
            c.learn = True
        elif low.startswith("mcs"):
            c.mcs["flag"] = part
        elif re.fullmatch(r"\d+(\.\d+)?d", part):
            c.est[c.owners[0]] = parse_est(part)
        elif "om=" in low or "kg=" in low:
            for kv in part.split():
                k, _, v = kv.partition("=")
                if k.lower() in ("om", "kg"):
                    c.est[k.lower()] = parse_est(v)
        else:
            c.errors.append(f"unknown meta token '{part}'")
    flag = c.mcs.pop("flag", None)
    for o in c.owners:
        if flag is None:
            c.mcs[o] = 0.0
        elif "=" in flag:
            c.mcs[o] = parse_est(flag.split("=", 1)[1])
        else:
            c.mcs[o] = c.est.get(o, 0.0)


def load() -> tuple[dict[str, Card], dict[Path, list[str]]]:
    cards: dict[str, Card] = {}
    texts: dict[Path, list[str]] = {}
    for prefix, path in BOARDS.items():
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        texts[path] = lines
        cur: Card | None = None
        for i, line in enumerate(lines):
            m = HEAD_RE.match(line.rstrip("\n"))
            is_heading = line.startswith("## ") or line.startswith("### ") or line.startswith("# ")
            if m or (is_heading and cur):
                if cur:
                    cur.end = i
                    cur = None
            if m:
                cur = Card(id=m.group(1), title=m.group(2), file=path, start=i, end=len(lines))
                if not cur.id.startswith(prefix):
                    cur.errors.append(f"{cur.id} is in {path.name} (expected prefix {prefix})")
                if cur.id in cards:
                    cur.errors.append(f"duplicate id {cur.id}")
                cards[cur.id] = cur
                continue
            if cur:
                fm = FIELD_RE.match(line.rstrip("\n"))
                if fm:
                    cur.fields[fm.group(1)] = fm.group(2)
        if cur:
            cur.end = len(lines)
    for c in cards.values():
        try:
            parse_meta(c, c.fields.get("meta", ""))
        except ValueError as e:
            c.errors.append(f"bad estimate {e}")
        for tok in re.split(r"[\s|]+", c.fields.get("refs", "")):
            for t in expand(tok):
                if t:
                    c.refs.add(t)
        if c.milestone:
            c.refs.add(c.milestone)
        c.skills = [t for t in re.split(r"[,\s]+", c.fields.get("skills", "")) if t]
    return cards, texts


def order_key(c: Card) -> tuple:
    return (
        MILESTONES.index(c.milestone) if c.milestone in MILESTONES else 9,
        PRIORITIES.index(c.priority) if c.priority in PRIORITIES else 9,
        c.id[:2] != "SH",
        c.start,
    )


def dep_state(cards: dict[str, Card], c: Card) -> tuple[bool, list[str]]:
    lines, ready = [], True
    for d in c.deps:
        dc = cards.get(d)
        st = dc.status if dc else "missing"
        ok = st in ("done", "review")
        ready &= ok
        who = "/".join(NAMES[o] for o in dc.owners) if dc else "?"
        lines.append(f"{'✓' if ok else '✗'} {d} ({who}, {st}){' — in review' if st == 'review' else ''}")
    return ready, lines


def mine(cards: dict[str, Card], owner: str | None) -> list[Card]:
    cs = [c for c in cards.values() if owner is None or owner in c.owners]
    return sorted(cs, key=order_key)


def fmt_card(c: Card, cards: dict[str, Card], texts: dict[Path, list[str]]) -> str:
    _, dl = dep_state(cards, c)
    out = c.text(texts[c.file])
    if dl:
        out += "  deps → " + "; ".join(dl) + "\n"
    if c.learn:
        out += "  learn → interview-critical: explain the design, let the human write the core logic, then review/test (unless learn_mode: off).\n"
    return out


def cmd_brief(args: list[str]) -> int:
    try:
        cards, _ = load()
        owner = detect_owner(opt(args, "--owner"))
        if not owner:
            print("[board] Owner unknown — copy CLAUDE.local.md.om.example or CLAUDE.local.md.kunal.example to CLAUDE.local.md (or set SL_OWNER).")
            return 0
        cs = mine(cards, owner)
        doing = [c for c in cs if c.status == "doing"]
        nxt = [c for c in cs if c.status == "todo" and dep_state(cards, c)[0]][:3]
        waiting = []
        for c in cs:
            if c.status == "todo":
                for d in c.deps:
                    dc = cards.get(d)
                    if dc and dc.status not in ("done", "review") and owner not in dc.owners:
                        waiting.append(f"{c.id}←{d}({dc.status})")
        parts = [f"[board] Working with {NAMES[owner]} (owner={owner})."]
        parts.append("Doing: " + (", ".join(f"{c.id} {c.title[:40]}" for c in doing) or "none"))
        parts.append("Next unblocked: " + (", ".join(c.id for c in nxt) or "none"))
        if waiting:
            parts.append("Waiting on teammate: " + ", ".join(waiting[:3]))
        print(" | ".join(parts))
        print("[board] Start with /next-task. Spec index: docs/spec/INDEX.md. Never read MASTER_SPEC.md whole.")
    except Exception as e:  # never break session start
        print(f"[board] unavailable ({type(e).__name__}: {e})")
    return 0


def cmd_next(args: list[str]) -> int:
    try:
        cards, texts = load()
        owner = detect_owner(opt(args, "--owner"))
        n = int(opt(args, "--n") or 2)
        ids = [a for a in args if re.fullmatch(r"(OM|KG|SH)-\d{2}", a)]
        if ids:
            for i in ids:
                print(fmt_card(cards[i], cards, texts) if i in cards else f"unknown task {i}\n")
            return 0
        if not owner:
            print("Owner unknown: create CLAUDE.local.md from the example for your name, or pass --owner om|kg.")
            return 0
        cs = mine(cards, owner)
        doing = [c for c in cs if c.status == "doing"]
        print(f"# Board for {NAMES[owner]}")
        if doing:
            print("## In progress (continue these first)")
            for c in doing:
                print(fmt_card(c, cards, texts))
            return 0
        ready = [c for c in cs if c.status == "todo" and dep_state(cards, c)[0]]
        if ready:
            print(f"## Next unblocked (top {min(n, len(ready))} of {len(ready)})")
            for c in ready[:n]:
                print(fmt_card(c, cards, texts))
        else:
            print("No unblocked todo tasks.")
        blocked = [c for c in cs if c.status == "todo" and not dep_state(cards, c)[0]][:3]
        if blocked:
            print("## Blocked (deps not done)")
            for c in blocked:
                print(f"- {c.id} {c.title}: " + "; ".join(l for l in dep_state(cards, c)[1] if l.startswith("✗")))
    except Exception as e:
        print(f"board error: {type(e).__name__}: {e}")
    return 0


def cmd_show(args: list[str]) -> int:
    cards, texts = load()
    ids = [a for a in args if re.fullmatch(r"(OM|KG|SH)-\d{2}", a)]
    if "--doing" in args and not ids:
        owner = detect_owner(opt(args, "--owner"))
        ids = [c.id for c in mine(cards, owner) if c.status == "doing"]
        if not ids:
            print("No task in status 'doing'. Pass an ID: /finish-task OM-05")
            return 0
    for i in ids:
        print(fmt_card(cards[i], cards, texts) if i in cards else f"unknown task {i}")
    return 0


def cmd_set(args: list[str]) -> int:
    if len(args) < 2:
        print("usage: set ID STATUS [--evidence TEXT]", file=sys.stderr)
        return 1
    tid, status = args[0], args[1].lower()
    evidence = opt(args, "--evidence")
    if status not in STATUSES:
        print(f"status must be one of {STATUSES}", file=sys.stderr)
        return 1
    cards, texts = load()
    c = cards.get(tid)
    if not c:
        print(f"unknown task {tid}", file=sys.stderr)
        return 1
    if status == "doing":
        r = subprocess.run([sys.executable, str(ROOT / "scripts/skills.py"), "check", tid], capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stdout.strip())
            print(f"Refusing to start {tid}: the skills gate is RED. Fix it (make skills-install CARD={tid}) and retry.", file=sys.stderr)
            return 1
    lines = texts[c.file]
    for i in range(c.start, c.end):
        if lines[i].startswith("- meta:"):
            lines[i] = re.sub(r"status:\s*\w+", f"status: {status}", lines[i])
    if evidence:
        ev_idx = next((i for i in range(c.start, c.end) if lines[i].startswith("- evidence:")), None)
        new = f"- evidence: {evidence}\n"
        if ev_idx is not None:
            lines[ev_idx] = new
        else:
            last = c.end
            while last > c.start and not lines[last - 1].strip():
                last -= 1
            lines.insert(last, new)
    c.file.write_text("".join(lines), encoding="utf-8")
    print(f"{tid} → {status}" + (f" (evidence: {evidence})" if evidence else ""))
    return 0


def required_ids() -> dict[str, list[str]]:
    r = lambda p, a, b, w=2: [f"{p}{str(i).zfill(w)}" for i in range(a, b + 1)]
    return {
        "Spec sections (§)": [f"§{i}" for i in range(28)],
        "Requirements": r("REQ-", 1, 16, 3),
        "Tests": r("T-DOM-", 1, 5) + r("T-AI-", 1, 3) + r("T-SEC-", 1, 7) + r("T-SWE-", 1, 5)
        + r("T-EVAL-", 1, 3) + r("T-UI-", 1, 2) + ["T-DOC-01"],
        "Milestones": MILESTONES,
        "Break types": r("B", 1, 8, 0),
        "Research Qs / hypotheses / exploratory": r("RQ", 1, 3, 0) + r("H", 1, 3, 0) + r("E", 1, 8, 0),
        "Invariants": r("I", 1, 12, 0),
        "Failure families": r("F", 1, 10, 0),
        "Threats": r("SEC-", 1, 14),
        "Metrics": r("MET-", 1, 12),
        "Quality attributes": r("NFR-", 1, 12),
        "Risks": r("RSK-", 1, 15),
        "Unresolved decisions (§25 #1-13)": r("U", 1, 13, 0),
        "Adopted ADRs": r("ADR-", 1, 12, 3),
    }


def cmd_check(args: list[str]) -> int:
    cards, _ = load()
    problems = []
    if not cards:
        problems.append("no cards found")
    for c in cards.values():
        problems += [f"{c.id}: {e}" for e in c.errors]
        if c.priority not in PRIORITIES:
            problems.append(f"{c.id}: missing priority")
        if c.milestone not in MILESTONES:
            problems.append(f"{c.id}: missing milestone")
        if c.status not in STATUSES:
            problems.append(f"{c.id}: bad status '{c.status}'")
        for o in c.owners:
            if o not in c.est:
                problems.append(f"{c.id}: missing estimate for {o}")
        if c.id.startswith("SH") and c.driver not in ("om", "kg"):
            problems.append(f"{c.id}: shared card needs driver: om|kg")
        for f_ in ("meta", "refs", "build", "done"):
            if f_ not in c.fields:
                problems.append(f"{c.id}: missing '- {f_}:' line")
        for d in c.deps:
            if d not in cards:
                problems.append(f"{c.id}: unknown dep {d}")
            elif d == c.id:
                problems.append(f"{c.id}: depends on itself")
    # cycles
    state: dict[str, int] = {}

    def visit(i: str, path: list[str]) -> None:
        if state.get(i) == 1:
            problems.append("dependency cycle: " + " → ".join(path + [i]))
            return
        if state.get(i) == 2 or i not in cards:
            return
        state[i] = 1
        for d in cards[i].deps:
            visit(d, path + [i])
        state[i] = 2

    for i in cards:
        visit(i, [])
    # coverage
    covered = set().union(*(c.refs for c in cards.values())) if cards else set()
    for group, ids in required_ids().items():
        missing = [i for i in ids if i not in covered]
        if missing:
            problems.append(f"uncovered {group}: {', '.join(missing)}")
    if problems:
        print("\n".join(problems))
        return 1
    n_ids = sum(len(v) for v in required_ids().values())
    print(f"board OK: {len(cards)} cards, {n_ids} spec IDs covered, deps acyclic")
    return 0


def cmd_trace(args: list[str]) -> int:
    cards, _ = load()
    out = [
        "# Traceability matrix",
        "",
        "GENERATED by `python3 scripts/board.py trace --write` from the task boards. Do not edit by hand.",
        "Every spec ID below maps to ≥1 task; `make board-check` fails CI if any ID loses its owner.",
        "",
    ]
    for group, ids in required_ids().items():
        out += [f"## {group}", "", "| ID | tasks (owner) |", "|---|---|"]
        for i in ids:
            ts = sorted((c for c in cards.values() if i in c.refs), key=order_key)
            cell = ", ".join(f"{c.id} ({'+'.join(NAMES[o] for o in c.owners)})" for c in ts) or "**UNCOVERED**"
            out.append(f"| {i} | {cell} |")
        out.append("")
    text = "\n".join(out)
    if "--write" in args:
        (TEAM / "TRACEABILITY.md").write_text(text, encoding="utf-8")
        print("wrote docs/team/TRACEABILITY.md")
    else:
        print(text)
    return 0


def summarize(cards: dict[str, Card]) -> dict:
    s = {o: {"total": 0.0, "p0": 0.0, "mcs": 0.0, "remaining": 0.0, "own": 0.0, "shared": 0.0, "n": 0,
             "status": {k: 0 for k in STATUSES}} for o in ("om", "kg")}
    for c in cards.values():
        for o in c.owners:
            e = c.est.get(o, 0.0)
            d = s[o]
            d["total"] += e
            d["shared" if c.id.startswith("SH") else "own"] += e
            d["p0"] += e if c.priority == "P0" else 0
            d["mcs"] += c.mcs.get(o, 0.0)
            d["remaining"] += e if c.status not in ("done", "cut") else 0
            d["n"] += 1
            d["status"][c.status] = d["status"].get(c.status, 0) + 1
    return s


def summary_md(cards: dict[str, Card]) -> str:
    s = summarize(cards)
    rows = ["| person | own tasks | shared share | total | P0 | MCS (min. credible scope) | cards |",
            "|---|---:|---:|---:|---:|---:|---:|"]
    for o in ("om", "kg"):
        d = s[o]
        rows.append(f"| {NAMES[o]} | {d['own']:.1f}d | {d['shared']:.1f}d | **{d['total']:.1f}d** | {d['p0']:.1f}d | "
                    f"{d['mcs']:.1f}d | {d['n']} |")
    gap = abs(s["om"]["total"] - s["kg"]["total"]) / max(s["om"]["total"], s["kg"]["total"], 1)
    rows.append("")
    rows.append(f"Balance gap: {gap:.1%} of the larger load. Estimates = focused days without AI assistance; "
                "use them to compare load, not to schedule. Re-estimate after M-1.")
    return "\n".join(rows)


def cmd_summary(args: list[str]) -> int:
    cards, _ = load()
    if "--brief" in args:
        s = summarize(cards)
        for o in ("om", "kg"):
            d = s[o]
            st = ", ".join(f"{k}={v}" for k, v in d["status"].items() if v)
            print(f"{NAMES[o]}: remaining {d['remaining']:.1f}d of {d['total']:.1f}d [{st}]")
        return 0
    md = summary_md(cards)
    if "--write" in args:
        plan = TEAM / "PLAN.md"
        txt = plan.read_text(encoding="utf-8")
        new = re.sub(r"(<!-- BEGIN:summary -->\n).*?(\n<!-- END:summary -->)", lambda m: m.group(1) + md + m.group(2), txt, flags=re.S)
        plan.write_text(new, encoding="utf-8")
        print("updated docs/team/PLAN.md summary block")
    else:
        print(md)
        s = summarize(cards)
        print("\nRemaining: " + " · ".join(f"{NAMES[o]} {s[o]['remaining']:.1f}d" for o in ("om", "kg")))
    return 0


def opt(args: list[str], name: str) -> str | None:
    if name in args:
        i = args.index(name)
        if i + 1 < len(args):
            return args[i + 1]
    return None


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    fn = {"brief": cmd_brief, "next": cmd_next, "show": cmd_show, "set": cmd_set, "check": cmd_check,
          "trace": cmd_trace, "summary": cmd_summary}.get(cmd)
    if not fn:
        print(f"unknown command {cmd}\n{__doc__}", file=sys.stderr)
        return 1
    return fn(rest)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
