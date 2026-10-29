# Second-Line 2.0 — team plan (Om × Kunal)

Status: PROPOSED — confirm or edit in SH-01, then run `make board-check`. Spec index: `docs/spec/INDEX.md`. Boards: `OM.md` · `KUNAL.md` · `SHARED.md`. Coverage proof: `TRACEABILITY.md` (generated).

## 1. The split in one line
**Om** builds what AUTHORIZES, VALIDATES, COMMITS and RECORDS (below the tool boundary). **Kunal** builds what ACTS, GENERATES TRUTH, MEASURES and ANALYZES (above it). Shared: contracts, domain decisions, the vertical slice, report, demo.

## 2. Why this split
- **Independence (§0, RSK-10, RSK-11).** The agent builder never builds the controls that constrain it. Cross-checks: Om attacks the agent with held-out injection packs (OM-16) and reviews the grader (KG-06) and the monitor rules (KG-11); Kunal red-teams the controls (KG-14) and verifies receipts with independent code (KG-12). Residual risk: Kunal builds both agent and supervisor — mitigated by Om's review and freezing monitor rules before eval.
- **One main stack each.** Om: Java/Spring + TypeScript (+ the small Python MCP adapter). Kunal: Python. Contracts are the only shared code.
- **Hardware.** Kunal's Apple Silicon unified memory runs 7–14B local models for the agent loop; Om's RTX 3050 (4 GB VRAM) only fits ≤4B smoke models. Experiments run on Explorer vLLM / API, never on laptop GPUs. Om holds the Explorer account; the open-weight arm runs on whichever laptop holds the tunnel.
- **Interview stories (§23).** Each person owns the components they'll be asked about; `learn` cards mark them.

## 3. Effort balance (generated — `make trace`)
<!-- BEGIN:summary -->
| person | own tasks | shared share | total | P0 | MCS (min. credible scope) | cards |
|---|---:|---:|---:|---:|---:|---:|
| Om | 55.5d | 11.8d | **67.2d** | 39.2d | 49.5d | 45 |
| Kunal | 51.5d | 12.0d | **63.5d** | 44.5d | 50.2d | 41 |

Balance gap: 5.6% of the larger load. Estimates = focused days without AI assistance; use them to compare load, not to schedule. Re-estimate after M-1.
<!-- END:summary -->

## 4. Interfaces — build against mocks, integrate at gates
Board `deps` = what you need to START. Integration lives in each card's `done`, so nobody waits idle.

| provider → consumer | artifact | mock until it's real |
|---|---|---|
| SH-02 → everyone | contracts v1 (schemas, errors, OpenAPI) | — |
| KG-03 → OM-04 | WorldBundle | packages/contracts/examples/world_bundle.min.json |
| OM-04 → KG-06 | ns export + state hash | examples/ns_export.min.json |
| OM-05 → OM-06 → KG-08 | gateway REST → MCP tools | Prism mock of openapi/gateway-tools.yaml · fake ToolClient |
| KG-06 scripted policies → OM-08…OM-11 | recorded action sequences | hand-written ProposedAction JSON |
| OM-12 + OM-13 → KG-11 | `:halt` endpoint + `ledger.events` | sample events JSONL · stub endpoint |
| OM-14 + SH-08 → KG-12 | receipt chain + test vectors | the vectors |
| OM-16 → KG-04 | attack packs | 2 placeholder payloads |
| OM-10 → KG-20 | policy bundle versions | — |
| KG-20 + KG-21 → OM-22 | replay + eval API | openapi/eval.yaml mock |

## 5. Milestone gates (demo each gate in the weekly sync)
| gate | exit evidence |
|---|---|
| M-0 | SH-01…06 accepted; contracts-v1.0.0 tagged; `make up PROFILES="core"` healthy on both machines; CI green |
| M-1 | dev split B1–B8 generates → loads → exports → grades; scripted oracle policy = 100% correct; property tests + balanced-but-wrong case exist; rules baseline graded on dev |
| M-2 | SH-07: a real LLM goes MCP → gateway → ledger on a B1 and a B7 case — graded and traced |
| M-3 | T-SEC-01/02/04/07, T-SWE-02/03, T-DOM-04 pass; receipt chain verifies (KG-12); supervisor halts a scripted toxic sequence; no dirty state after negative tests |
| M-4 | prereg frozen before any eval run; pilot gate recorded; campaigns complete or honestly truncated; H1–H3 analyzed with CIs; both replay modes shown with verified hashes |
| M-5 | console core, chaos + load results, datasheet + model cards, demo from a clean clone, report; SH-18 audit |

## 6. Phase plan (sequencing, not dates)
Each phase ≈ one week of solid part-time work each. Estimates are unassisted focused days: Claude Code speeds up implementation-heavy cards (~1.5–2×), not integration, debugging or campaign wall-clock. Rough fit at ~4 focused days/week each: **full scope ≥ 8–10 weeks; MCS ≥ 6–7 weeks.** If Module 7 is closer, apply §7 now and tell the instructor in week 1 — never shrink the experiment silently.

| phase | Om | Kunal | gate |
|---|---|---|---|
| 1 | SH-01/02/03/05, OM-01, OM-25, OM-02 | SH-01/02/04/06, KG-01, KG-02 | M-0 |
| 2 | OM-03, OM-04 | KG-03, KG-05, KG-04 (start) | |
| 3 | OM-04 (finish), OM-05, OM-06 | KG-04, KG-06, KG-07 | M-1 |
| 4 | OM-05/06 (finish), OM-07, OM-08, SH-19 | KG-08, KG-09, KG-10, SH-07, SH-19 | M-2 |
| 5 | OM-08, OM-09, OM-10, OM-11 | KG-11, KG-13, KG-15, KG-12 | |
| 6 | OM-12, OM-13, OM-14, OM-15, OM-16 | KG-15, KG-16, KG-17, KG-14 | M-3 + pilot gate |
| 7 | OM-17, OM-18, OM-20, OM-21 + campaign shard 2/2 | KG-18, KG-20, KG-19 (start) | |
| 8 | OM-19, OM-22, OM-23, OM-24, SH-16/17 | KG-19, KG-21, KG-22, SH-13, SH-15 | M-5 + SH-18 |

## 7. Minimum credible scope (MCS) & cut order (§20)
MCS = cards tagged `mcs` (`mcs=Xd` = reduced scope); totals in §3. Cut in this order:
1. **Console extras + load scale:** OM-22 → static result pages; OM-19 → 10 concurrent runs; OM-21 → approvals + run trace only.
2. **Crypto anchors + broad chaos:** OM-14 → unsigned chain + checkpoints; OM-18 → four key faults; OM-17 → Jaeger only; KG-14 → bypass, race, toxic sequence.
3. **Commercial-model expansion:** shrink or drop the frontier arm (300 runs) and disclose it; drop KG-21 (console reads result files); fewer paired-live replications in KG-20.

**Protected:** correct financial model (OM-03/04/08) · real tool-using LLM (OM-05/06, KG-08/09/10) · pre-commit safety (OM-07…11) · independent grading (KG-06) · core 3-condition experiment (OM-13, KG-11, KG-15…19) · honest evidence (SH-15/16/18).
**Experiment shortfall rule:** decide in KG-17, before any eval run, as an AMENDMENT. Cut the frontier arm before cutting repeats — H3 needs 5 repeats per scenario.

## 8. Collaboration protocol
- **Om owns CI/CD and approves + merges every PR** (ruleset on main: PR + 1 approval + code-owner review + required checks). Kunal opens PRs with `/open-pr` and never merges; Om reviews with `/review-pr <n>` within 24 h.
- Om's own PRs: green CI + Kunal's approval (independence of controls), then Om merges. No ruleset bypass on `main`; only Om can merge (`merge-gate`). Details + break-glass: docs/setup/GITHUB.md (OM-25).
- Branch `<owner>/<TASK-ID>-slug`; Conventional Commits with the task ID; small PRs.
- Skills gate GREEN before any card (`make skills-check`); task skills are re-checked when a card goes `doing`.
- Contracts change only through a PR both approve + `/handoff` + `make codegen`.
- ADR before any trust-boundary change (`/adr`); registered-design changes only through `/amend`.
- Weekly 30-minute sync (demo the slice, walk the boards, unblock interfaces); `/standup` on other days.
- One Claude Code task per session; `/clear` between tasks.

## 9. Machine roles
| | Om — Vivobook Pro 15 (Windows 11 + WSL2) | Kunal — MacBook Pro 14" (Apple Silicon) |
|---|---|---|
| daily dev | Java/Spring, console, infra inside WSL2 (≤10 GB) | Python natively; agent loop with a local model |
| local LLM | ≤4B smoke model (4 GB VRAM) | 7–14B via Ollama/Metal, by RAM tier |
| stack | compose profiles, never all at once | full stack if ≥18 GB, else profiles |
| campaigns | open-weight shards while you hold the tunnel | frontier + rules shards; reference latency host when you hold the tunnel |
| Explorer HPC | account holder; runs `make hpc-*` | requests an account (SH-19); owns the vLLM config + model choice |
| GitHub | admin: rulesets, secrets, CI, merges | write: branches + PRs |

## 10. Calendar (fill in during SH-01)
| item | value |
|---|---|
| Module 7 final submission | TBD (not yet announced) |
| Weekly sync slot | TBD |
| M-0 … M-5 target dates | TBD (set once the submission date is known) |
| Kunal's Mac chip / unified memory | Apple M4 / 16 GB |
| Kunal's GitHub handle | @kunalgupta06 (Write, added 2026-10-24) |
| Kunal's Explorer account status | approved ☑ |
