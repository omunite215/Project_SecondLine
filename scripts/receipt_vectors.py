#!/usr/bin/env python3
"""Receipt canonicalization + hash-chain test vectors (SH-08, §9 §12, T-SEC-05, ADR-012).

Writes packages/contracts/test-vectors/receipts/{jcs.json,chain.json} from a stdlib RFC 8785 (JCS)
restricted to integers, and holds the reference chain verifier that defines each vector's expected
result. OM-14 (Java) and KG-12 (audit-verifier) must reproduce the vectors; this is not the verifier.
Deterministic: fixed inputs, no clock, no randomness. Signature vectors wait for ADR-018 (SH-09).

usage: receipt_vectors.py [--out DIR] [--check]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "packages" / "contracts" / "test-vectors" / "receipts"
# Must equal x-receipt-hash.exclude in receipts/decision_receipt.schema.json (kit test pins it).
EXCLUDE = ("receipt_hash", "signature", "signature_key_id")
MAX_SAFE = 2**53 - 1
LIMITATION = "undetectable_without_checkpoint"


def _no_duplicates(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError(f"duplicate key in {keys}")
    return dict(pairs)


def _no_float(text):
    raise ValueError(f"non-integer number {text} (money and prices are strings)")


def parse(text: str):
    """Strict I-JSON parse: duplicate keys, fractions, exponents and NaN/Infinity raise ValueError."""
    return json.loads(text, object_pairs_hook=_no_duplicates, parse_float=_no_float, parse_constant=_no_float)


def _string(s: str) -> str:
    if any(0xD800 <= ord(c) <= 0xDFFF for c in s):
        raise ValueError("lone surrogate is not I-JSON")
    return json.dumps(s, ensure_ascii=False)


def jcs(o) -> str:
    """RFC 8785 canonical form for integer-only documents."""
    if isinstance(o, dict):
        keys = sorted(o, key=lambda k: k.encode("utf-16-be"))  # UTF-16 code-unit order, RFC 8785 §3.2.3
        return "{" + ",".join(_string(k) + ":" + jcs(o[k]) for k in keys) + "}"
    if isinstance(o, list):
        return "[" + ",".join(jcs(x) for x in o) + "]"
    if o is True:
        return "true"
    if o is False:
        return "false"
    if o is None:
        return "null"
    if isinstance(o, int):
        if abs(o) > MAX_SAFE:
            raise ValueError(f"integer {o} outside ±(2^53−1)")
        return str(o)
    if isinstance(o, str):
        return _string(o)
    raise ValueError(f"not canonicalizable: {o!r}")


def sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def hashed_view(receipt: dict) -> dict:
    return {k: v for k, v in receipt.items() if k not in EXCLUDE}


def receipt_hash(receipt: dict) -> str:
    return sha256(jcs(hashed_view(receipt)))


def verify_chain(receipts: list[dict]) -> dict:
    """Reference verdict for a receipt list. The verdict set is closed: the first MALFORMED, HASH_MISMATCH
    or LINK_BROKEN (with its index), else ok. Anything unparseable is MALFORMED, never ok, and an empty
    chain is MALFORMED. A chain alone can't show that receipts were dropped from the end, so an intact
    chain still reports the limitation."""
    if not isinstance(receipts, list) or not receipts:
        return {"ok": False, "reason": "MALFORMED", "index": 0}
    prev = "GENESIS"
    for i, r in enumerate(receipts):
        if not (isinstance(r, dict) and isinstance(r.get("receipt_hash"), str)
                and isinstance(r.get("previous_receipt_hash"), str)):
            return {"ok": False, "reason": "MALFORMED", "index": i}
        try:
            actual = receipt_hash(r)
        except ValueError:
            return {"ok": False, "reason": "MALFORMED", "index": i}
        if actual != r["receipt_hash"]:
            return {"ok": False, "reason": "HASH_MISMATCH", "index": i}
        if r.get("previous_receipt_hash") != prev:
            return {"ok": False, "reason": "LINK_BROKEN", "index": i}
        prev = r["receipt_hash"]
    return {"ok": True, "limitation": LIMITATION}


JCS_CASES = [
    ("rfc8785_3.2.3_key_sort",
     '{"\\u20ac":"Euro Sign","\\r":"Carriage Return","\\ufb33":"Hebrew Letter Dalet With Dagesh","1":"One",'
     '"\\ud83d\\ude00":"Emoji: Grinning Face","\\u0080":"Control","\\u00f6":"Latin Small Letter O With Diaeresis"}'),
    ("escapes_short_forms", '{"s":"q\\" b\\\\ \\b\\f\\n\\r\\t"}'),
    ("escapes_other_controls_lowercase_hex", '{"s":"\\u0001\\u001f\\u000b"}'),
    ("no_escape_for_del_slash_non_ascii", '{"s":"\\u007f / \\/ \\u00e9 \\u4e2d"}'),
    ("non_bmp_literal", '{"s":"\\ud834\\udd1e"}'),
    ("whitespace_removed", ' { "b" : [ 1 , 2 ] ,\n "a" : { } } '),
    ("nested_objects_sorted", '{"z":{"y":{"x":1,"w":2},"v":3},"a":{"c":1,"b":2}}'),
    ("array_order_kept", '[3,1,2,[{"b":1,"a":2}]]'),
    ("empty_object_and_array", '{"o":{},"a":[]}'),
    ("literals", '{"t":true,"f":false,"n":null}'),
    ("minus_zero_is_zero", '[-0,0]'),
    ("safe_integer_bounds", '[9007199254740991,-9007199254740991]'),
    ("decimal_strings_untouched", '{"amount":"1000.50","fx":"1.08745","qty":"-0"}'),
    ("key_sort_is_utf16_not_codepoint", '{"\\uff61":1,"\\ud83d\\ude00":2}'),
]
MUST_REJECT = [
    ("fraction", '{"a":1.5}'),
    ("integral_fraction", '{"a":1.0}'),
    ("exponent", '{"a":1e2}'),
    ("above_safe_integer", '[9007199254740992]'),
    ("below_safe_integer", '[-9007199254740992]'),
    ("lone_high_surrogate", '{"s":"\\ud800"}'),
    ("lone_low_surrogate_key", '{"\\udc00":1}'),
    ("duplicate_key", '{"a":1,"a":2}'),
    ("trailing_tokens", '{"a":1} {"b":2}'),
    ("nan", '[NaN]'),
]


def jcs_vectors() -> dict:
    cases = []
    for name, text in JCS_CASES:
        canonical = jcs(parse(text))
        cases.append({"name": name, "input": text, "canonical": canonical, "sha256": sha256(canonical)})
    for name, text in MUST_REJECT:
        try:
            jcs(parse(text))
        except ValueError:
            continue
        raise SystemExit(f"must_reject case {name} was accepted")
    return {
        "$comment": "SH-08 / RFC 8785 JCS restricted to integers (golden rule 3). `input` is raw JSON text; "
                    "`canonical` is the JCS string; sha256 is over its UTF-8 bytes. Every must_reject input "
                    "must fail to canonicalize. Generated by scripts/receipt_vectors.py; do not edit.",
        "cases": cases,
        "must_reject": [{"name": n, "input": t} for n, t in MUST_REJECT],
    }


def _uuid(n: int) -> str:
    return f"5e0{n:05d}-0000-4000-8000-{n:012d}"


def _receipts() -> list[dict]:
    bundle = sha256("synthetic policy bundle v1")
    specs = [
        {"decision": "ALLOW", "evidence_validation": "VALID"},
        {"decision": "REVIEW_REQUIRED", "evidence_validation": "VALID", "error_code": "REVIEW_REQUIRED"},
        {"decision": "DENY", "evidence_validation": "INVALID", "error_code": "POLICY_DENIED"},
        {"decision": "EXECUTED", "evidence_validation": "VALID", "approval_id": _uuid(901),
         "ledger_transaction_id": _uuid(902)},
        {"decision": "DENY", "evidence_validation": "VALID", "error_code": "STATE_CONFLICT"},
    ]
    out, prev = [], "GENESIS"
    for i, extra in enumerate(specs, start=1):
        r = {"receipt_version": "1.0", "receipt_id": _uuid(100 + i), "action_id": _uuid(200 + i),
             "action_digest": sha256(f"synthetic action {i}"), "policy_decision_id": _uuid(300 + i),
             "policy_bundle_hash": bundle, "previous_receipt_hash": prev,
             "issued_at": f"2026-10-30T12:00:0{i}.{i:03d}Z", **extra}
        r["receipt_hash"] = receipt_hash(r)
        out.append(r)
        prev = r["receipt_hash"]
    return out


def chain_vectors() -> dict:
    chain = _receipts()

    def copy():
        return [dict(r) for r in chain]

    edited = copy()
    edited[2]["decision"] = "ALLOW"  # a DENY rewritten as ALLOW, hash left alone
    rehashed = copy()
    rehashed[2]["decision"] = "ALLOW"
    rehashed[2]["receipt_hash"] = receipt_hash(rehashed[2])
    removed = copy()
    del removed[2]
    swapped = copy()
    swapped[1], swapped[2] = swapped[2], swapped[1]
    malformed = copy()
    malformed[1] = "not a receipt"
    no_hash = copy()
    del no_hash[2]["receipt_hash"]
    no_prev = copy()
    del no_prev[0]["previous_receipt_hash"]
    tamper = [("edited_no_rehash", edited), ("edited_rehashed", rehashed), ("removed", removed),
              ("swapped", swapped), ("truncated_tail", copy()[:-1]), ("empty_chain", []),
              ("malformed_entry", malformed), ("missing_receipt_hash", no_hash),
              ("missing_previous_receipt_hash", no_prev)]
    return {
        "$comment": "SH-08 / ADR-012: receipt_hash = sha256 over the JCS of the receipt minus x-receipt-hash.exclude; "
                    "previous_receipt_hash links the chain from GENESIS. Verdicts are a closed set: MALFORMED, HASH_MISMATCH, "
                    "LINK_BROKEN (first bad index) or ok. All data is synthetic. A chain without an "
                    "ADR-018 checkpoint cannot detect a dropped tail (T-SEC-05 limitation). Generated by "
                    "scripts/receipt_vectors.py; do not edit.",
        "x-receipt-hash": {"exclude": list(EXCLUDE)},
        "receipts": [{"receipt": r, "canonical": jcs(hashed_view(r))} for r in chain],
        "tamper": [{"name": n, "receipts": rs, "expect": verify_chain(rs)} for n, rs in tamper],
    }


def render() -> dict[str, str]:
    return {name: json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
            for name, doc in (("jcs.json", jcs_vectors()), ("chain.json", chain_vectors()))}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--check", action="store_true", help="exit 1 if --out differs from a fresh run; write nothing")
    args = ap.parse_args(argv)
    files = render()
    if args.check:
        stale = [n for n, text in files.items()
                 if not (args.out / n).exists() or (args.out / n).read_text(encoding="utf-8") != text]
        for n in stale:
            print(f"stale: {n} (run `python3 scripts/receipt_vectors.py`)")
        return 1 if stale else 0
    args.out.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (args.out / name).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
