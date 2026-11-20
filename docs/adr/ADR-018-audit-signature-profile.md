# ADR-018: Audit threat model & receipt signature profile
Status: PROPOSED (om ☐ kunal ☐, PR #34)
Date: 2026-10-30 · Resolves: U9 (§25) · Spec: §11 (SEC-09) §12 · ADR-012 · REQ-009 · T-SEC-05 · RSK-09 · Tasks affected: SH-08 part 2 (signature + checkpoint vectors), OM-14 (receipts), KG-12 (audit-verifier)

## Context
§12 requires tamper-evident receipts for every decision, action and denial (ADR-012). It warns that "a simple hash chain without trusted external checkpoint is NOT strong tamper-resistance to privileged rewriting", and it leaves the signature profile (algorithm, canonicalization, key rotation) to an ADR. SH-08 part 1 (#33) fixes `receipt_hash`: sha256 over the JCS of the receipt minus `x-receipt-hash.exclude`, chained from `GENESIS`. It also shows in the vectors that a chain alone can't detect a dropped tail. This ADR names the attackers, says what signatures and checkpoints add, and states plainly what the verifier still can't see.

## Attacker models (SEC-09)
| # | attacker | can do | chain only | + signed checkpoint, digest outside the DB |
|---|---|---|---|---|
| A1 | accidental corruption (bug, partial write, bad migration) | flips or drops bytes | **detected** (HASH_MISMATCH / LINK_BROKEN) | detected |
| A2 | non-privileged service or agent | nothing: only the ledger role writes `audit_receipts` (OM-01 DB roles), and the table is append-only | n/a, blocked by DB grants (T-SEC-01) | n/a |
| A3 | privileged rewrite **without** the signing key (DB superuser, compromised ledger DB credentials) | edits, deletes, reorders, recomputes every hash | edit/delete/reorder **undetectable** if the whole suffix is rehashed; truncation undetectable | **detected** up to the last checkpoint: the rewritten chain no longer reaches the checkpointed `last_receipt_hash`, and the attacker can't re-sign. A dropped tail after the last checkpoint stays undetectable. |
| A4 | privileged rewrite **with** the signing key (full ledger-host compromise) | everything A3 can, plus re-signing | undetectable | detected **only** for history before a checkpoint whose digest already sits outside their reach (git-committed). Anything after it is undetectable. |

The verifier must report the A3 and A4 residue as a limitation, never as "verified" (T-SEC-05 "limited inability to detect"). The SH-08 vectors already do this (`undetectable_without_checkpoint`).

## Options (signature profile)
1. **Ed25519 over the UTF-8 bytes of the `receipt_hash` string (`"sha256:<hex>"`)** (recommended). There's a single canonicalization (JCS, already vectored). Ed25519 is built into the JDK (`EdDSA`, Java 15+) and into Python `cryptography`, and it's deterministic, so signature vectors are reproducible. Its weakness: `signature_key_id` isn't bound by the hash. That's harmless, because swapping it to another published key makes verification fail.
2. **Ed25519 over the JCS bytes of the full receipt including `signature_key_id`.** This binds the key id, but it needs a second canonical view and a second set of vectors, and gains no security over 1.
3. **HMAC-SHA256 with a shared secret.** Simplest, but any verifier that holds the key can also forge. It isn't independent verification, so it fails SEC-09.

## Decision (proposed)
- **What gets signed:**
  - **Checkpoints, always.** One every 50 receipts per chain, and one at run end.
  - Per-receipt `signature` stays optional, off by default (ADR-012 "as time allows").
  - A checkpoint is `{checkpoint_version, chain_scope, count, last_receipt_hash, issued_at, signature_key_id, signature}`. It gets a new contract schema in part 2.
- **Algorithm:** Option 1. Ed25519 (RFC 8032) over the UTF-8 bytes of the hash string: `receipt_hash` for receipts, and for checkpoints the sha256 of the checkpoint's JCS minus `signature`. The signature is base64url without padding.
- **Chain scope:** one chain per ledger namespace (ADR-015). `chain_scope` is the namespace id, which never reveals the split (ADR-015 ID rules).
- **Keys:**
  - `signature_key_id` = `sl-receipt-<env>-v<N>`.
  - The private key is a PEM file **outside the repo**; its path is in env var `SL_RECEIPT_SIGNING_KEY`, read only by the ledger. It never appears in logs or traces (OM-15).
  - Public keys live in the repo at `infra/keys/receipt-public-keys.json`, as `{key_id, public_key, not_before, not_after}`.
  - **Rotation:** issue `v<N+1>`, and keep old public keys for verification. **Expiry:** the verifier rejects a signature whose `issued_at` falls outside that key's window.
  - The only key in the repo is the SH-08 test-only keypair, under `packages/contracts/test-vectors/receipts/`. It's named `sl-receipt-test-v1` and carries a gitleaks allowlist entry for that exact path. The ledger refuses any key id containing `-test-` outside tests.
- **Anchor:** every checkpoint is written to a file outside the ledger DB (the run's artifact directory). Its sha256 goes into the run manifest, and that digest is git-committed with the campaign results. That puts A3, and A4 before that commit, out of the attacker's reach.

## Consequences (tests, tasks, risks)
- SH-08 part 2:
  - signature vectors for the 5-receipt chain, using the test key;
  - checkpoint vectors;
  - tamper cases for a forged signature, a wrong key id, an expired key, and a chain that doesn't reach its checkpoint.
- OM-14 implements signing and checkpoints. KG-12 verifies them offline, using only public keys plus the committed digest.
- New contract: `receipts/checkpoint.schema.json`, plus the public-key list format.
- **Risk RSK-09:** a single-host demo means the ledger holds both the DB and the key, so A4 is realistic. Mitigation and claim limit: the report says "tamper-evident up to the last externally anchored checkpoint", never "tamper-proof".

## Verification (how we'll know it holds)
- T-SEC-05 runs, using the SH-08 vectors plus OM-14 integration tests:
  - modify, remove or reorder a receipt before a checkpoint → detected;
  - after the last checkpoint → reported as a limitation.
- A forged or expired signature is rejected by both the Java and Python implementations on the same vectors.
- `gitleaks` stays green with only the test-key path allowlisted.
