# Decision register
Status values: ADOPTED (in the spec) · PROPOSED · ACCEPTED (both approved in a PR) · SUPERSEDED. Create/update with `/adr`.

## Adopted in the spec (§25 — canonical text in docs/spec/sections/25-*.md)
| ADR | decision |
|---|---|
| 001 | One-bank cash-equity reconciliation; platform abstraction is secondary |
| 002 | Java/Spring/Postgres holds financial authority; Python never writes the DB directly |
| 003 | Real LLM tool calls plus a deterministic rules baseline |
| 004 | Pre-commit checking is mandatory; async monitors can't retroactively stop a commit |
| 005 | MCP tools versioned, independently authenticated, least-privilege |
| 006 | Independent financial-truth grader; balance alone is insufficient |
| 007 | Two replay modes with isolated state reset |
| 008 | Keep registered H1–H3; disclose amendments and exploration |
| 009 | Docker Compose before Kubernetes; local live demo with model fallback |
| 010 | Prioritize proof over extra frameworks |
| 011 | Approval digest binds action + evidence version + state; durable idempotency in the DB |
| 012 | Audit receipts include denied actions; independent signed checkpoint as time allows |

## Project ADRs
| ADR | title | status | resolves | file |
|---|---|---|---|---|
| 013 | Java gateway as policy enforcement point + thin Python MCP adapter | ACCEPTED (SH-02, PR #11) | U3 (part) | ADR-013-service-boundaries-mcp-adapter.md |
| 014 | Control conditions off/monitor/full + shortcut affordances | ACCEPTED (SH-05, PR #13 + #17) | U4 | ADR-014-control-conditions.md |
| 015 | Run namespaces, snapshots, hidden-truth isolation | ACCEPTED (SH-02, PR #11) | — | ADR-015-namespaces-truth-isolation.md |
| 016 | Accounting model & precision | ACCEPTED (SH-03, PR #10) | U1 | ADR-016-accounting-model.md |
| 017 | Evidence semantics & detection gap | ACCEPTED (SH-04, PR #16) | U5 | ADR-017-evidence-semantics.md |
| 018 | Audit threat model | to write (SH-09) | U9 | — |

## Unresolved decisions (§25 items 1–13 → U1–U13)
| U | topic | resolved by | status |
|---|---|---|---|
| U1 | accounting model | SH-03 → ADR-016 | resolved (ADR-016, PR #10) |
| U2 | baseline model IDs | KG-10 → model-selection ADR | open |
| U3 | MCP spec + transport | SH-02 → ADR-013 | resolved (ADR-013: mcp==2.3.0, spec 2026-07-28, Streamable HTTP; OM-06 re-verifies) |
| U4 | policy / identity matrix | SH-05 → ADR-014 | resolved (ADR-014; thresholds by method, numbers after KG-03) |
| U5 | evidence semantics | SH-04 → ADR-017 | resolved (ADR-017) |
| U6 | per-hypothesis denominators | SH-06 → prereg | open |
| U7 | research amendments (paired pressure) | KG-16 | open |
| U8 | external validation | SH-11 | open |
| U9 | audit threat model | SH-09 → ADR-018 | open |
| U10 | contract versioning | SH-02 (single API v1) | resolved (one API v1; legacy v1/v2 demo skipped; archived runs replay against their contracts-vX tag) |
| U11 | metrics + budgets | KG-17 → SH-10 | open |
| U12 | team assignments | SH-01 (this plan) | resolved (PR #1, 2026-10-27) |
| U13 | source reconciliation | SH-13 | open |
