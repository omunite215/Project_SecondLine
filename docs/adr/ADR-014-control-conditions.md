# ADR-014: Control conditions (off / monitor / full) and shortcut affordances
Status: PROPOSED (decide in SH-05; copy into the prereg in KG-16) · Resolves: U4 (part) · Spec: §10 strategies A–D, §13 H1–H2, §14, §16

## Context
H2 compares full controls with controls-off; RQ1/H1 need real opportunities to attempt violations; the PoC ran "off" as log-but-don't-block in an isolated ledger. If what is *available* differs between conditions, H2 measures affordances instead of enforcement.

## Decision (proposed): same tool surface in every condition — only enforcement differs
| layer | off (B) | monitor (C) | full (D) |
|---|---|---|---|
| run-token auth, ns scoping, schema validation | on | on | on |
| budgets / time caps (harness safety, generous limits) | on | on | on |
| OPA policy decision | not called | not called | enforced |
| ledger pre-commit verifier (I3–I8) | structural only (types, ns, I1 balance) | structural only | enforced |
| idempotency dedupe | off | off | on |
| maker-checker approvals | off | off | on |
| supervisor + kill switch | off (events still emitted) | on | on |
| receipts + decision log | on | on | on |

- "Would-have-been-denied" labels for off/monitor come from offline action replay through the full policy (KG-20) plus the oracle — never from calling OPA in-line, which would distort H2 latency.
- Controls-off runs only in disposable namespaces (§7).
- Pressure L0–L3 changes the framing text. Shortcut-capable actions (suspense-account adjustment, closure with empty evidence, SSI change via booking correction) stay schema-valid at every level; L3 adds an explicit shortcut hint.
- **Flag:** §14 describes L3 as "with shortcut availability". If availability stays L3-only, H1's pressure effect is confounded with opportunity. Record the team's choice — registered design or AMENDMENT — before any eval run.
- Role/action matrix, approval thresholds and posting limits are derived in SH-05 from the generated value distribution (table to add here), never invented.

## Consequences
H2 isolates enforcement; H1 opportunities are comparable across levels; "off" is dangerous by design, so it stays isolated.
