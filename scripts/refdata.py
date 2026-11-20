#!/usr/bin/env python3
"""Public reference-data snapshots (KG-02; §6, REQ-001, SEC-14, RSK-15). Plan: docs/plans/KG-02.md.

  fetch --date YYYY-MM-DD   download ECB + Fed H.10 FX, a GLEIF LEI subset, write the curated ISO 20022 codes;
                            every file hashed into data/reference/MANIFEST.json (human-run: needs network)
  verify                    re-hash every MANIFEST file, flag unlisted files and a stale DATASHEET_INPUTS.md
                            (no network; CI and `make refdata-verify`)

FX rates are stored as published, as decimal strings, never cross-filled between sources (§6: information-only,
not executable prices). Stdlib only. No credentials, no personal data: a generic User-Agent.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "data" / "reference"
UA = "refdata-snapshot/0.1 (synthetic research dataset)"
CURRENCIES = ("USD", "EUR", "GBP", "CHF", "JPY")  # ADR-016
FX_START = "2026-01-02"
GLEIF_COUNTRIES = ("US", "GB", "DE", "CH", "JP")
GLEIF_PER_COUNTRY = 100
H10_PACKAGE = "60f32914ab61dfab590e0e470153e3ae"  # Fed DDP: H.10 daily, all currencies
TOP_LEVEL = {"MANIFEST.json", "DATASHEET_INPUTS.md"}

# R4: curated, not fetched. Every row stays `verify: true` until SH-13 checks it against the ISO code set.
ISO_CITATION = "https://www.iso20022.org/catalogue-messages/additional-content-messages/external-code-sets"
# SH-13 (docs/sources-verification.md §2): meanings confirmed against the ECB T2S Programme Office slides
# (bibliography #12) and T2S change requests 0355-URD / 0621-SYS. CYCL was not found and is dropped.
T2S_CITATION = ("https://www.ecb.europa.eu/paym/target/t2s/profuse/shared/pdf/"
                "insights_on_multiple_statuses_in_a_status_notification.pdf")
_ISO = [
    ("LACK", "pending_reason", "Lack of securities: the delivering party lacks the securities", "B7 (sell leg)"),
    ("MONY", "pending_reason", "Insufficient money: the paying party lacks the cash", "B7 (buy: our cash)"),
    ("CLAC", "pending_reason", "Counterparty insufficient securities", "B7 (buy: counterparty can't deliver)"),
    ("CMON", "pending_reason", "Counterparty insufficient money", "B7 (sell leg)"),
    ("LATE", "pending_reason", "Market deadline missed", "B1"),
]


# ---- parsers (pure; tested on fixture text) -------------------------------------------------------------
def parse_ecb(text: str) -> list[dict[str, str]]:
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        if r.get("OBS_VALUE") and r["CURRENCY"] in CURRENCIES:
            rows.append({"date": r["TIME_PERIOD"], "base": r["CURRENCY_DENOM"], "quote": r["CURRENCY"],
                         "rate": r["OBS_VALUE"]})
    return sorted(rows, key=lambda x: (x["date"], x["quote"]))


def parse_h10(text: str) -> tuple[list[dict[str, str]], int]:
    """Fed DDP 'seriescolumn' CSV. `RXI$US_N.B.XX` = USD per foreign unit; `RXI_N.B.XX` = foreign per USD."""
    lines = list(csv.reader(io.StringIO(text)))
    head = next((i for i, ln in enumerate(lines) if ln and ln[0] == "Time Period"), None)
    if head is None:
        raise ValueError("H.10: response has no 'Time Period' header (empty or changed format)")
    ccys = next(ln for ln in lines if ln and ln[0] == "Currency:")[1:]
    series = lines[head][1:]
    rows, dropped = [], 0
    for ln in lines[head + 1:]:
        if not ln or not ln[0][:4].isdigit():
            continue
        for ccy, sid, val in zip(ccys, series, ln[1:], strict=False):
            if ccy not in CURRENCIES:
                continue
            if val in ("ND", ""):
                dropped += 1
                continue
            base, quote = (ccy, "USD") if sid.startswith("RXI$US") else ("USD", ccy)
            rows.append({"date": ln[0], "base": base, "quote": quote, "rate": val})
    return sorted(rows, key=lambda x: (x["date"], x["base"], x["quote"])), dropped


def aligned_dates(ecb: list[dict[str, str]], h10: list[dict[str, str]]) -> list[str]:
    """R2: dates both sources published; a cross-source comparison may use only these."""
    return sorted({r["date"] for r in ecb} & {r["date"] for r in h10})


EXCLUDED_CATEGORIES = {"SOLE_PROPRIETOR"}  # a natural person's name is personal data (golden rule 2)


def parse_gleif(pages: list[dict[str, Any]]) -> list[dict[str, str]]:
    out = []
    for page in pages:
        for rec in page.get("data", []):
            a = rec["attributes"]
            e, reg = a["entity"], a["registration"]
            if e.get("category") in EXCLUDED_CATEGORIES:
                continue
            out.append({"lei": a["lei"], "legal_name": e["legalName"]["name"], "country": e["legalAddress"]["country"],
                        "category": e.get("category") or "", "entity_status": e.get("status") or "",
                        "registration_status": reg["status"], "last_update": reg.get("lastUpdateDate") or ""})
    return sorted(out, key=lambda r: r["lei"])


def iso_codes() -> list[dict[str, Any]]:
    return [{"code": c, "kind": k, "meaning": m, "used_by": u, "citation": T2S_CITATION, "verify": False}
            for c, k, m, u in _ISO]


# ---- snapshots, MANIFEST, verify, datasheet -------------------------------------------------------------
def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def dump_rows(rows: Any) -> bytes:
    return (json.dumps(rows, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode()


def _load_manifest(root: Path) -> dict[str, Any]:
    p = root / "MANIFEST.json"
    return json.loads(p.read_text()) if p.is_file() else {"manifest_version": "1.0", "snapshots": []}


def _write_manifest(root: Path, manifest: dict[str, Any]) -> None:
    manifest["snapshots"] = sorted(manifest["snapshots"], key=lambda s: s["ref"])
    (root / "MANIFEST.json").write_bytes(dump_rows(manifest))


def write_snapshot(root: Path, *, source: str, date: str, files: dict[str, bytes], meta: dict[str, Any],
                   rows: dict[str, int]) -> dict[str, Any]:
    base = root / source / date
    base.mkdir(parents=True, exist_ok=True)
    listed = []
    for name in sorted(files):
        (base / name).write_bytes(files[name])
        f: dict[str, Any] = {"path": f"{source}/{date}/{name}", "sha256": _sha(files[name]), "bytes": len(files[name])}
        if name in rows:
            f["rows"] = rows[name]
        listed.append(f)
    keep = {k: v for k, v in meta.items() if k not in ("ref", "source", "date", "files")}
    entry = {"ref": f"{source}@{date}", "source": source, "date": date, **keep, "files": listed}
    manifest = _load_manifest(root)
    manifest["snapshots"] = [s for s in manifest["snapshots"] if s["ref"] != entry["ref"]] + [entry]
    _write_manifest(root, manifest)
    return entry


def verify(root: Path) -> list[str]:
    errors: list[str] = []
    manifest = _load_manifest(root)
    listed = set()
    for s in manifest["snapshots"]:
        for f in s["files"]:
            listed.add(f["path"])
            p = root / f["path"]
            if not p.is_file():
                errors.append(f"{f['path']}: missing")
            elif _sha(p.read_bytes()) != f["sha256"]:
                errors.append(f"{f['path']}: sha256 mismatch")
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_file() and rel not in TOP_LEVEL and rel not in listed:
            errors.append(f"{rel}: not in MANIFEST")
    return errors


def datasheet(manifest: dict[str, Any]) -> str:
    out = ["# Reference-data inputs (generated from MANIFEST.json by `scripts/refdata.py`; KG-02 → KG-22 datasheet)",
           "", "Do not edit by hand. Synthetic-world inputs only: public reference data, no client data.", ""]
    for s in manifest["snapshots"]:
        out += [f"## {s['ref']}", "",
                f"- source: {s['source']} · retrieved_at: {s.get('retrieved_at', '')}",
                f"- license: {s.get('license', '')} ({s.get('license_url', '')})",
                f"- needs verification (SH-13): {'yes' if s.get('verify') else 'no'}"]
        out += [f"- url: {u}" for u in s.get("url", [])]
        out += [f"- coverage gap: {g}" for g in s.get("coverage_gaps", [])]
        out += [f"- caveat: {c}" for c in s.get("caveats", [])]
        out += ["", "| file | rows | sha256 |", "|---|---|---|"]
        out += [f"| {f['path']} | {f.get('rows', '')} | `{f['sha256'][:19]}…` |" for f in s["files"]]
        out.append("")
    return "\n".join(out)


# ---- fetch (network; human-run) -------------------------------------------------------------------------
def lf(data: bytes) -> bytes:
    """Store text downloads with LF endings and a final newline (the repo's pre-commit hooks enforce both), so
    the hashed bytes are the committed bytes. Recorded as a caveat on each raw file's snapshot."""
    out = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return out if out.endswith(b"\n") else out + b"\n"


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})  # noqa: S310 — fixed https URLs below
    with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310
        return bytes(r.read())


def _now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(root: Path, snap_date: str) -> None:
    fx_end = (date.fromisoformat(snap_date) - timedelta(days=1)).isoformat()
    quotes = "+".join(c for c in CURRENCIES if c != "EUR")
    ecb_url = (f"https://data-api.ecb.europa.eu/service/data/EXR/D.{quotes}.EUR.SP00.A"
               f"?format=csvdata&startPeriod={FX_START}&endPeriod={fx_end}")
    raw = lf(_get(ecb_url))
    ecb = parse_ecb(raw.decode())
    write_snapshot(root, source="ecb", date=snap_date, files={"raw.csv": raw, "rates.json": dump_rows(ecb)},
                   rows={"rates.json": len(ecb)}, meta={
                       "url": [ecb_url], "retrieved_at": _now(), "verify": True,
                       "license": "ECB statistics: free reuse with source acknowledgement",
                       "license_url": "https://www.ecb.europa.eu/home/disclaimer/html/index.en.html",
                       "coverage_gaps": ["no rates on weekends or TARGET holidays",
                                         f"pairs USD, GBP, CHF, JPY per EUR only; window {FX_START}..{fx_end}"],
                       "caveats": ["information-only reference rates, not executable transaction prices (§6)",
                                   "concertation 14:15 CET; published around 16:00 CET",
                                   "raw.csv stored with LF line endings (normalized from the download)"]})
    # The DDP returns an empty body for from/to ranges, so take the last 260 observations and cut to the window.
    h10_url = (f"https://www.federalreserve.gov/datadownload/Output.aspx?rel=H10&series={H10_PACKAGE}"
               "&lastobs=260&from=&to=&filetype=csv&label=include&layout=seriescolumn")
    raw = lf(_get(h10_url))
    all_h10, dropped = parse_h10(raw.decode())
    h10 = [r for r in all_h10 if FX_START <= r["date"] <= fx_end]
    last_h10 = max(r["date"] for r in h10)
    aligned = aligned_dates(ecb, h10)
    write_snapshot(root, source="h10", date=snap_date,
                   files={"raw.csv": raw, "rates.json": dump_rows(h10), "aligned_with_ecb.json": dump_rows(aligned)},
                   rows={"rates.json": len(h10), "aligned_with_ecb.json": len(aligned)}, meta={
                       "url": [h10_url], "retrieved_at": _now(), "verify": True,
                       "license": "Federal Reserve Board statistical release; public data, cite the Board",
                       "license_url": "https://www.federalreserve.gov/data.htm",
                       "coverage_gaps": [f"window {FX_START}..{last_h10}: H.10 is published weekly with a lag",
                                         f"{dropped} 'ND' (no data) observations in the raw download dropped, e.g. US holidays",
                                         "EUR and GBP quoted as USD per unit; CHF and JPY as units per USD"],
                       "caveats": ["noon buying rates in New York: different methodology and timing from ECB (§6)",
                                   "compare with ECB only on aligned_with_ecb.json dates; never exchangeable",
                                   "raw.csv stored with LF line endings (normalized from the download)"]})
    pages, urls = [], []
    for c in GLEIF_COUNTRIES:
        url = ("https://api.gleif.org/api/v1/lei-records?filter%5Bentity.legalAddress.country%5D=" + c +
               f"&filter%5Bregistration.status%5D=ISSUED&sort=lei&page%5Bsize%5D={GLEIF_PER_COUNTRY}&page%5Bnumber%5D=1")
        pages.append(json.loads(_get(url)))
        urls.append(url)
    leis = parse_gleif(pages)
    excluded = sum(len(p.get("data", [])) for p in pages) - len(leis)
    write_snapshot(root, source="gleif", date=snap_date, files={"lei_subset.json": dump_rows(leis)},
                   rows={"lei_subset.json": len(leis)}, meta={
                       "url": urls, "retrieved_at": _now(), "verify": False,
                       "license": "CC0 1.0 (GLEIF LEI data)",
                       "license_url": "https://www.gleif.org/en/meta/lei-data-terms-of-use",
                       "coverage_gaps": [f"first {GLEIF_PER_COUNTRY} ISSUED LEIs by LEI per {', '.join(GLEIF_COUNTRIES)}"
                                         "; not representative", "no BIC or settlement-account mapping fetched",
                                         f"{excluded} SOLE_PROPRIETOR record(s) excluded (natural persons)"],
                       "caveats": ["an LEI identifies a legal entity, not a settlement account (§6)"]})
    write_iso(root, snap_date)
    (root / "DATASHEET_INPUTS.md").write_text(datasheet(_load_manifest(root)))


def write_iso(root: Path, snap_date: str) -> None:
    """The curated ISO 20022 / T2S code snapshot (no network)."""
    iso = iso_codes()
    write_snapshot(root, source="iso20022", date=snap_date, files={"settlement_codes.json": dump_rows(iso)},
                   rows={"settlement_codes.json": len(iso)}, meta={
                       "url": [T2S_CITATION, ISO_CITATION], "retrieved_at": _now(), "verify": False,
                       "license": "curated from public ISO 20022 / ECB T2S documentation (codes and meanings only)",
                       "license_url": ISO_CITATION,
                       "coverage_gaps": ["curated, not fetched: pending/failing reason codes used by B1/B7 only"],
                       "caveats": ["meanings confirmed against ECB T2S sources in SH-13 (docs/sources-verification.md)",
                                   "factory trades are buys: only MONY and CLAC apply to B7 (SH-13)"]})


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--root", type=Path, default=REF)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--date", required=True)
    sub.add_parser("verify")
    i = sub.add_parser("iso", help="rewrite only the curated ISO 20022 snapshot (no network)")
    i.add_argument("--date", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "fetch":
        a.root.mkdir(parents=True, exist_ok=True)
        fetch(a.root, a.date)
    if a.cmd == "iso":
        write_iso(a.root, a.date)
        (a.root / "DATASHEET_INPUTS.md").write_text(datasheet(_load_manifest(a.root)))
    errors = verify(a.root)
    ds = a.root / "DATASHEET_INPUTS.md"
    if not ds.is_file() or ds.read_text() != datasheet(_load_manifest(a.root)):
        errors.append("DATASHEET_INPUTS.md: stale (run `make refdata-fetch` or regenerate)")
    for e in errors:
        print(f"refdata: {e}")
    n = len(_load_manifest(a.root)["snapshots"])
    print(f"refdata: {n} snapshot(s) " + ("verified" if not errors else f"— {len(errors)} problem(s)"))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
