# Shared tasks (SH-*) — both people, one driver

The driver owns the outcome and schedules the session; the other person contributes the listed share. `U#` = unresolved decision #n in §25. ADRs stay PROPOSED until both approve in the PR — the defaults written here let work start; override them in the ADR.

## M-0 Contracts & decisions

### SH-01 · Kickoff: confirm split, calendar, machines, repo
- meta: P0 | M-0 | om=0.25d kg=0.25d | mcs | driver: om | deps: — | status: review
- refs: §20 §21 | U12 | RSK-12
- build: 45-minute call: walk PLAN.md and both boards, edit anything you disagree with, rerun `make board-check`; fill the PLAN.md §10 calendar; Kunal records exact chip/RAM in KUNAL.md and CLAUDE.local.md; create the private repo, add both, protect main (1 approving review + CODEOWNERS), Om adds Kunal as collaborator (Write) and applies the ruleset (OM-25); each person creates CLAUDE.local.md + .claude/settings.local.json from the examples, then runs `make skills-install BIN=1` → `make skills-check` (GREEN required before any other card); Kunal files the Explorer access request (SH-19).
- done: docs/adr/README.md marks U12 resolved; skills gate GREEN and `make kit-check` green on both machines; this kit merged through a cross-reviewed PR.
- evidence: U12 resolved in docs/adr/README.md; kit merged via PR #1 (approved by Kunal); skills gate GREEN + make kit-check green on Om's machine 2026-10-28, Kunal reports GREEN; PLAN §10 dates TBD

### SH-02 · Contracts v1: schemas, errors, OpenAPI skeletons
- meta: P0 | M-0 | om=1d kg=1d | mcs | driver: om | deps: SH-01 | status: todo
- refs: §9 §10 §8 §12 §4 | REQ-004 REQ-005 REQ-007 | T-DOM-03 | ADR-005 ADR-013 ADR-015 | U3 U10
- build: packages/contracts: tools/<tool>.{input,output}.schema.json for every §10 tool; actions/proposed_action; receipts/decision_receipt; scenario/{manifest, world_bundle, truth (x-privileged)}; attacks/attack_pack; events/envelope (§12 fields); errors.json (§8 codes); openapi/{gateway-tools, ledger-internal, ledger-admin, review, eval}.yaml skeletons; examples/ (§9 documents, minimal world bundle, minimal ns export); VERSION 1.0.0; scripts/contracts_check.py. Om drafts gateway / ledger / receipt / event / errors; Kunal drafts world_bundle / truth / manifest / attack_pack. One API v1 with idempotency + reason codes; the legacy v1/v2 deprecation demo is skipped and recorded (U10). Pin MCP SDK + spec revision in ADR-013 (U3).
- done: `make contracts-check` passes; both approve; git tag contracts-v1.0.0; ADR-013 and ADR-015 ACCEPTED.

### SH-03 · ADR-016 accounting model & precision
- meta: P0 | M-0 | om=0.75d kg=0.25d | mcs | driver: om | deps: SH-01 | status: todo
- refs: §5 §9 §1 | U1 | ADR-001 ADR-002 | REQ-002 | I1 I2 | B1..B8 | NFR-02
- build: docs/adr/ADR-016-accounting-model.md + docs/domain.md: cash journal vs securities position ledger; position projection; synthetic chart of accounts (nostro cash, custody, suspense, rounding P&L, FX revaluation); precision per ISO 4217 minor units, quantity, price, FX; rounding + B3 tolerance policy; permitted adjustment categories; reversal semantics; expected state delta for each B1–B8 pattern; one synthetic bank only.
- done: ACCEPTED by both; its tables are referenced by KG-03/KG-04 truth and OM-08 validators.

### SH-04 · ADR-017 evidence semantics & detection gap
- meta: P0 | M-0 | om=0.25d kg=0.75d | mcs | driver: kg | deps: SH-01 | status: todo
- refs: §5 §8 §25 | U5 | REQ-006 | I5 | T-DOM-04 | F3
- build: per break type: which record is authoritative (custodian statement vs internal booking vs settlement status), which evidence_refs a valid action must cite, which wrong outcomes the runtime verifier can detect synchronously (no truth access) vs only the oracle — list the detection-gap cases explicitly.
- done: ACCEPTED; the table is consumed by OM-08 and KG-06.

### SH-05 · ADR-014 control conditions, policy matrix, shortcut affordances
- meta: P0 | M-0 | om=0.5d kg=0.5d | mcs | driver: om | deps: SH-01 | status: todo
- refs: §10 §11 §13 §14 | U4 | REQ-005 REQ-010 | H1 H2 | F1 F2
- build: finalize the PROPOSED draft docs/adr/ADR-014: behavior of off / monitor / full at gateway, ledger and supervisor; tool surface + shortcut affordances per pressure level (keep the surface identical across conditions); role-action matrix, approval thresholds, suspense rules and posting limits derived from the generated value distribution (no magic numbers).
- done: ACCEPTED before OM-10, OM-16, KG-04 and KG-09 start; copied into the prereg (KG-16).

### SH-06 · Metric denominators & estimators
- meta: P0 | M-0 | om=0.25d kg=0.75d | mcs | driver: kg | deps: SH-04, SH-05 | status: todo
- refs: §14 §13 | U6 | MET-01..12 | H1 H2 H3 | REQ-007 REQ-014
- build: draft experiments/prereg/preregistration.md §Metrics: numerator + denominator for MET-01..12, unit of analysis, H1 "applicable opportunity", H2 latency span start/end (Om defines the gateway span boundaries), pass^k estimator (all-k, not pass@k), cluster structure.
- done: both sign off; frozen later in KG-16.

### SH-14 · Integration cadence (ongoing)
- meta: P1 | M-0 | om=1d kg=1d | mcs | driver: om | deps: SH-01 | status: todo
- refs: §21 §20 | NFR-07 | ADR-010 | RSK-01 RSK-12 RSK-14
- build: weekly 30-minute sync (demo the current slice, board review, unblock interfaces); cross-review every PR within 24 h; contract changes only with /handoff; /standup on non-sync days; refuse new tools without a requirement + measured benefit (ADR-010).
- done: recurring — mark done at course end.

## M-2 Integration gate

### SH-07 · Vertical slice end-to-end (M-2 gate)
- meta: P0 | M-2 | om=1d kg=1d | mcs | driver: kg | deps: OM-04, OM-05, OM-06, KG-06, KG-08 | status: todo
- refs: §20 §10 §8 §4 | REQ-004 | T-AI-01 | RSK-01
- build: one B1 (timing) and one B7 (shortfall → escalate) dev case end to end: factory → load ns → create run (controls=off) → agent via MCP → gateway → ledger → export → grade; trace visible (Jaeger if available, else logs); record the action sequence as a labeled scripted fallback.
- done: `make run-one SCN=<id> CONTROLS=off` passes on both machines with no manual DB patches; graded outcome stored.

### SH-19 · Explorer HPC access & Claude-safe SSH bridge
- meta: P1 | M-2 | om=0.75d kg=0.25d | driver: om | deps: SH-01 | status: todo
- refs: §7 §22 §6 | U2 | RSK-04 RSK-13 | NFR-11
- build: Om: ed25519 key via ssh-copy-id, ~/.ssh/config alias `explorer` with ControlMaster (docs/setup/EXPLORER-HPC.md); `make hpc-check` green from inside Claude Code with no prompt; scratch + log dirs; first `make hpc-up` with Kunal's filled infra/hpc/vllm.sbatch on a small model; tunnel + health. Kunal: file the Research Computing Access Request (sponsor: the instructor) and record its status; until approved, Om runs hpc-up/tunnel for KG-10, KG-17 and KG-18. No model training — Explorer only serves inference.
- done: hpc-check and hpc-health pass through the tunnel; no credential ever typed into Claude; Kunal's account status recorded in PLAN.md §10.

## M-3 Audit

### SH-08 · Receipt canonicalization test vectors
- meta: P1 | M-3 | om=0.5d kg=0.25d | driver: om | deps: SH-02 | status: todo
- refs: §9 §12 | REQ-009 | T-SEC-05 | SEC-09 | ADR-012
- build: packages/contracts/test-vectors/receipts: RFC 8785 inputs/outputs, sha256 digests, a test-only Ed25519 keypair, signatures, a 5-receipt chain incl. one DENY.
- done: Java (OM-14) and Python (KG-12) both pass the same vectors in CI.

### SH-09 · ADR-018 audit threat model
- meta: P1 | M-3 | om=0.5d kg=0.25d | driver: om | deps: SH-02 | status: todo
- refs: §11 §12 | U9 | ADR-012 | SEC-09 | T-SEC-05 | RSK-09
- build: attacker models addressed (accidental corruption, non-privileged tamper, privileged DB rewrite with / without an external anchor); key storage (outside the repo, path via env), rotation / expiry; anchor technique (periodic checkpoint file + git-committed digest); what the verifier can and cannot detect.
- done: ACCEPTED; OM-14 and KG-12 implement it.

## M-4 Science

### SH-10 · Pilot-grounded budgets & thresholds
- meta: P1 | M-4 | om=0.25d kg=0.25d | driver: kg | deps: KG-17 | status: todo
- refs: §22 §14 §18 | U11 | NFR-08 NFR-09 | RSK-04 RSK-05
- build: set run budgets (tool calls, time, cost), dashboard latency targets, observability retention and fallback thresholds from pilot data; update OM-12 config and campaign configs.
- done: numbers committed with a link to the pilot evidence.

### SH-11 · External blind set & financial validity review
- meta: P1 | M-4 | om=0.25d kg=0.5d | driver: kg | deps: KG-04 | status: todo
- refs: §6 §14 | U8 | T-EVAL-02 T-DOM-02 | RSK-02 RSK-11
- build: recruit a classmate or practitioner to author 20–30 hard cases from the factory template without seeing monitor logic; domain review of 20–30 generated cases; otherwise record the explicit lack of review.
- done: blind set stored in data/generated/blind/ (deny-read for Claude); review notes in docs/data-governance.md.

## M-5 Delivery

### SH-12 · Risk-control matrix & governance crosswalk
- meta: P1 | M-5 | om=0.5d kg=0.5d | driver: om | deps: OM-10, KG-14 | status: todo
- refs: §3 §11 §21 | F1..F10 | SEC-01..14 | REQ-015 | NFR-05
- build: docs/risk-control-matrix.md: F1–F10 and SEC-01–14 → preventive / detective control → test ID → evidence → result; crosswalk to NIST AI RMF (Govern / Map / Measure / Manage), NIST GenAI profile, FINOS AIGF agentic risks, OWASP LLM06 and BCBS 239, stating "mapping ≠ compliance".
- done: every row links a test or states the gap; the claims rule passes.

### SH-13 · Source reconciliation & citation verification
- meta: P1 | M-5 | om=0.25d kg=0.5d | driver: kg | deps: SH-01 | status: todo
- refs: §2 §16 §24 §6 | U13 | RSK-15 | B7 B8
- build: try to reconcile PoC 1,035 vs 729 from the original logs (else keep both as POC-REPORTED with a note); verify ISO 20022 / T2S codes (LACK, MONY, CLAC, CMON, LATE) and BIC↔LEI caveats against official sources; verify the DOI/URL of every reference used in the report; mark each VERIFY item resolved or unresolved.
- done: docs/sources-verification.md with a status per claim.

### SH-15 · Final report / paper
- meta: P0 | M-5 | om=2d kg=2.5d | mcs | driver: kg | deps: KG-19, OM-24 | status: todo
- refs: §13 §14 §16 §23 §24 §2 | REQ-015 | H1 H2 H3 | RQ1 RQ2 RQ3 | E1..E8 | T-EVAL-01 | RSK-14
- skills: document-skills
- build: docs/report/: Om — architecture, security results, reliability / chaos / load, platform limitations; Kunal — methods, data, experiments, H1–H3 with CIs, exploratory E1–E8 kept separate, PoC history labeled POC-REPORTED, limitations; shared — abstract, conclusions, test-limited recommendation.
- done: the claims rule passes; every number links to a manifest or result file.

### SH-16 · Demo script, rehearsal, recording
- meta: P0 | M-5 | om=1d kg=0.75d | mcs | driver: om | deps: OM-23, KG-18 | status: todo
- refs: §17 | T-UI-02 | RSK-13 | NFR-11
- skills: document-skills
- build: docs/demo-script.md following the §17 7-step timing; one legitimate success and one blocked/escalated case; clearly labeled fallback recording; rehearse twice on the demo machine.
- done: 5–7 minute run from a clean environment via make demo-*; video file + link committed.

### SH-17 · README, recruiter case study, claim audit
- meta: P1 | M-5 | om=0.5d kg=0.5d | driver: om | deps: SH-15 | status: todo
- refs: §1 §23 §0 §26 | REQ-015 | T-DOC-01
- build: README (real-vs-stub table, quickstart, results with denominators, §26 post-course roadmap marked not built), docs/case-study.md, per-person contributions; claim audit with contract-guardian + the claims rule.
- done: a classmate reproduces the smoke subset from the README alone (T-DOC-01).

### SH-18 · Final definition-of-done audit (§27)
- meta: P0 | M-5 | om=0.25d kg=0.25d | mcs | driver: om | deps: SH-15, SH-16, SH-17 | status: todo
- refs: §27 §19 | T-DOC-01 | REQ-001..016
- build: walk the §27 definition-of-done checklist and doc QA checks; link each item to a commit, test log or artifact; list unmet items honestly in the report's limitations.
- done: every §27 box is checked with evidence or explicitly marked unmet.
