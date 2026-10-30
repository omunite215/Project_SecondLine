# Handoff: Om → Kunal · receipt canonicalization + chain vectors, part 1 (2026-10-30)
Task: SH-08 (part 1; Om drives) · §9 §12 · REQ-009 · T-SEC-05 · SEC-09 · ADR-012 · contracts VERSION 1.0.0 → 1.1.0. #32 also bumps to 1.1.0. #32 merges first, and this PR re-bumps to 1.2.0 before it merges, so two different 1.1.0 contracts never exist.

## What changed
- `receipts/decision_receipt.schema.json` gains `x-receipt-hash: {exclude: [receipt_hash, signature, signature_key_id]}`.
  - `receipt_hash` = `sha256:` + hex(SHA-256(UTF-8(JCS(receipt minus exclude)))).
  - Optional fields are hashed when present.
  - `previous_receipt_hash` is part of the hash. The first receipt uses `"GENESIS"`.
- `scripts/contracts_check.py` rejects any exclude list that leaves `receipt_hash` in, names an unknown field, or drops a required field from the hash.
- `packages/contracts/test-vectors/receipts/`:
  - **`jcs.json`:** 14 `{input, canonical, sha256}` cases and 10 `must_reject` inputs. Among the cases:
    - the RFC 8785 §3.2.3 sort example;
    - escapes;
    - non-BMP characters;
    - a case where UTF-16 order differs from code-point order;
    - safe-integer bounds.
  - **`chain.json`:** 5 synthetic receipts: ALLOW → REVIEW_REQUIRED → **DENY** → EXECUTED → DENY.
    - Each has its canonical form and hash.
    - There are 9 tamper cases, each with the expected verdict:
      - edited, edited and rehashed, removed, swapped, truncated tail;
      - empty chain, malformed entry, missing `receipt_hash`, missing `previous_receipt_hash`.
      The kit test hard-codes every expected verdict, so the vectors don't confirm themselves.
- Generator plus reference verifier: `scripts/receipt_vectors.py`. It's stdlib only and deterministic, and `--check` runs in the kit.
- POC-REPORTED (one-off run, not yet in CI): the Java `CanonicalJson` from #32 reproduces all 14 JCS cases and rejects all 10 must-reject inputs. The permanent version is `OM_02_jcs_matches_sh08_vectors`, added to libs/contracts-java once both PRs are on main.
- Not yet independently checked: the `chain.json` hashes. Only this generator has computed them, so OM-14 (Java) and KG-12 will be the first independent checks.

## How to use it now (KG-12)
- Load both files. For each JCS case, `canonical == jcs(input)` and `sha256 == sha256(canonical)`. Every `must_reject` input must raise.
- For each tamper case, your verifier's verdict must match `expect`. The verdict set is **closed**:
  - `MALFORMED`, `HASH_MISMATCH` or `LINK_BROKEN` at the first bad index;
  - otherwise `ok` with the `undetectable_without_checkpoint` limitation.
  - An empty chain, a non-object entry or a missing hash field is `MALFORMED`, never ok.
- Truncation can't be detected from the chain alone. That is the honest T-SEC-05 result until ADR-018's checkpoint exists.

## Pending (part 2, after ADR-018 is ACCEPTED)
- Ed25519 signature vectors and the test-only keypair.
- Whether `signature_key_id` belongs inside the hash (VERIFY, provisional). While it's outside, a verifier must resolve keys only from the pinned public-key list and never trust the key id in the receipt. Moving it inside later breaks every hash, so it has to be settled before anything real produces receipts.
- Checkpoint vectors.
- ADR-018 is drafted as PROPOSED in its own PR (SH-09).

## Breaking?
No. Nothing computed `receipt_hash` before this.

## What I need back
1. Do you agree with the exclude list? In particular, `signature_key_id` sits outside the hash.
2. Is the expected-result shape (`{ok, reason, index}` / `{ok, limitation}`) usable as KG-12's output, or do you want a different verdict format before I freeze it?
