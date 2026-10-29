# Kunal Gupta — board (Intelligence & Evidence)

Owner key `kg` (`owner: kunal` in CLAUDE.local.md). Claude reads this through `python3 scripts/board.py next` (prints only the cards it needs) — keep the card format exact.
**Role:** PR author — open PRs with `/open-pr`; Om approves and merges. Explorer: request your own account (SH-19); Om runs `make hpc-*` until it's approved.
**Scope:** everything that ACTS, GENERATES TRUTH, MEASURES and ANALYZES — scenario factory + truth, reference-data snapshots, oracle grader, rules baseline, LangGraph agent, prompts, model serving, supervisor, audit verifier, platform red-team, experiment runner, prereg, pilot, campaigns, statistics, replay, eval API, datasheet/model cards. Om attacks your agent with held-out packs (OM-16) and reviews your grader + monitor rules; you red-team his controls (KG-14) and verify his receipts with independent code (KG-12).
**Machine:** MacBook Air, Apple M4, 16 GB unified memory (recorded SH-01, 2026-10-28). Native Python + Ollama (Metal) for the agent dev loop; Docker only for the other services. Local model tier (Q4): 16 GB → 7–8B · 18–24 GB → ≤14B · 36 GB+ → ~30B. Reference latency host for H2: record machine specs in every campaign manifest.
**Legend:** `meta` = priority | milestone | estimate (focused days, no AI assist) | `mcs` in minimum credible scope (`mcs=Xd` reduced) | `learn` interview-critical | `skills:` task skills the card requires (gate-checked) | deps (needed to START; integration lives in `done`) | status.

## M-0 Contracts & setup

### KG-01 · Python workspace, codegen, CI jobs
- meta: P0 | M-0 | 1d | mcs | deps: SH-01 | status: todo
- refs: §7 §19 §21 | NFR-06 NFR-11 | T-DOC-01
- build: uv workspace (Python 3.12) with members services/agent, services/mcp-adapter (Om's code, your workspace), services/supervisor, packages/scenario-factory, packages/evaluation, packages/audit-verifier, packages/contracts/py; ruff + mypy (strict for factory/evaluation) + pytest + hypothesis config; `make codegen-py` (datamodel-code-generator → `sl_contracts` pydantic models, Decimal for money); multi-arch Dockerfiles for Python services; path-filtered CI job.
- done: `make test-py` green on both machines; codegen deterministic (CI fails on diff).

## M-1 Truthful simulator (truth side)

### KG-02 · Public reference-data snapshots (GLEIF, ECB, H.10, ISO codes)
- meta: P1 | M-1 | 2d | deps: KG-01 | status: todo
- refs: §6 | REQ-001 | SEC-14 | RSK-15 | U13 | B4 B7 B8
- build: scripts/refdata fetchers → data/reference/<source>/<date>/ + MANIFEST.json (URL, retrieval time, license, sha256, row counts, coverage gaps): small GLEIF subset (≤500 LEIs, CC0; an LEI is not a settlement account), ECB euro reference rates (information-only, not executable prices), Fed H.10 for chosen pairs on aligned dates only, ISO 20022 / T2S status + reason codes with citations and `verify: true` until SH-13 confirms. JPMorgan synthetic data = optional, never a blocker.
- done: `make refdata-verify` re-hashes every snapshot; the factory reads refdata only via MANIFEST; datasheet inputs recorded.

### KG-03 · Causal break factory core (world, lifecycle, B1–B3)
- meta: P0 | M-1 | 3d | mcs | deps: KG-01, SH-02, SH-03 | status: todo
- refs: §5 §6 | REQ-001 | T-DOM-02 | ADR-006 | B1 B2 B3 | F10
- build: packages/scenario-factory/sl_factory: seeded world (institution, counterparties, instruments, cash accounts); lifecycle simulator that produces causal events FIRST (trade → booking → confirmation → SSI → custodian updates → settled / failed / partial), then the visible records. Outputs per contracts: WorldBundle (visible; opaque ids; symptoms only, never root-cause labels) + Truth (causal_event_ids, root_cause, allowed/forbidden outcomes, required_evidence_ids, approval_requirements, expected_state_delta, escalation_if_insufficient_evidence, severity, generator version, explanation, canary SLCANARY-<hex>) + manifest with sha256. Generators: B1 timing (timezones, as-of), B2 quantity (incl. partial-settlement look-alike), B3 price/rounding at the tolerance boundary.
- done: same seed ⇒ identical hash; property test: no truth field or value leaks into the bundle; `make factory SPLIT=dev N=40` writes data/generated/dev/.

### KG-04 · Factory: B4–B8, hard variants, categories, splits
- meta: P0 | M-1 | 3.5d | mcs=2.5d | deps: KG-03, KG-02, SH-05 | status: todo
- refs: §5 §14 §15 §6 | REQ-001 REQ-012 | T-DOM-02 T-EVAL-02 | B4 B5 B6 B7 B8 | E2 | F3 F4 F10 | H1 | ADR-014 | RSK-02
- build: B4 FX source / time / holiday / stale rate; B5 missing vs duplicate vs legitimately separate executions; B6 corporate action with wrong ex-date / entitlement; B7 shortfall (escalate; codes pending SH-13); B8 SSI mismatch (escalate; tempting reference-data edit); every §5 hard variant; the 11 §5 scenario categories incl. ≥1 balanced-but-false case and missing-evidence abstention; pressure L0–L3 + injection flags per ADR-014 (placeholder payloads until OM-16 packs land); dev / eval / blind template + parameter split with a fingerprint check; eval = 200 scenarios, 4 pressure × 2 injection × 25, with an explicit break-type balance table; matched-pressure variants for the exploratory amendment.
- done: `make factory-all` reproducible; stratification + balance tables printed; split-overlap check passes; eval/blind outputs land only in data/generated/{eval,blind}/.

### KG-05 · Leakage, split-integrity & canary checks
- meta: P0 | M-1 | 1d | mcs | deps: KG-03 | status: todo
- refs: §5 §6 §15 | REQ-006 | T-DOM-03 T-SEC-06 | F10 | SEC-11 | RSK-11
- build: scripts/leakage + `make leakage-check` + CI job: scan prompts, MCP tool descriptions, recorded tool responses, traces/logs and the console bundle for canaries and truth field names; template-fingerprint overlap dev vs eval/blind; assert visible ids are opaque.
- done: a planted canary in a test trace fails CI; the clean tree passes.

### KG-06 · Independent oracle grader & metric primitives
- meta: P0 | M-1 | 3.5d | mcs | learn | deps: KG-03, SH-04, SH-06 | status: todo
- refs: §5 §14 §8 | REQ-006 REQ-007 | T-DOM-02 T-DOM-04 T-AI-03 | ADR-006 | MET-01..08 | F8 | SEC-05 | RSK-10
- build: packages/evaluation/sl_eval/grader: inputs = Truth + ledger ns export (OM-04) + action / decision / receipt log; per-proposal labels (violation type, applicable opportunity), per-committed-action harm labels, per-break outcome (correct resolution | correct escalation | false closure | masked | unresolved | wrong escalation), state-delta comparison against expected_state_delta; scenario- and run-level rollups with the SH-06 denominators; agent narrative ignored as evidence. Re-implement scripted policies oracle / shortcut / retry / sloppy as golden drivers (§16 concepts, fresh code).
- done: golden suite green (scripted oracle = 100% correct; the others reproduce their expected labels); Om reviews the grader PR; ORACLE_MISMATCH reported, never auto-fixed; integration test against a real OM-04 export.

### KG-07 · Deterministic rules baseline (strategy A)
- meta: P0 | M-1 | 2.5d | mcs | deps: KG-06 | status: todo
- refs: §10 §14 | REQ-003 | T-AI-02 | ADR-003 | E1
- build: services/agent/sl_agent/strategies/rules: per-break-type rules over structured fields only, behind the same ToolClient interface the LLM uses (fake/direct backend now, MCP backend once OM-06 lands) — no extra data access; escalate when no rule applies; tag cases that need free-text interpretation.
- done: runs and is graded on the dev split; parity test proves the MCP backend exposes exactly the LLM's tool surface; E1 notes on where rules suffice.

## M-2 Real agent

### KG-08 · LangGraph agent (graph, budgets, approvals, model-agnostic)
- meta: P0 | M-2 | 4d | mcs | learn | deps: KG-01, SH-02 | status: todo
- refs: §10 §8 | REQ-004 | T-AI-01 | ADR-003 | F8 | SEC-13
- skills: langgraph-fundamentals, langgraph-persistence
- build: services/agent/sl_agent/graph: START → retrieve_case → reconcile_facts → evaluate_sufficiency → choose (classify | correct | escalate) → call_tool → {approval_wait (interrupt + poll) | denial branch | commit} → verify_result → finalize with evidence + uncertainty. Structured ProposedAction from sl_contracts (schema errors recorded); max tool calls / time / tokens, no escalation loops; checkpoint/resume by run_id; a denial is never treated as permission; model client = OpenAI-compatible endpoint (Ollama / vLLM) or provider SDK, settings recorded; model-timeout handling (chaos row); store a structured plan + justification, not hidden chain-of-thought. Build on a fake ToolClient + fake LLM; switch to the OM-06 MCP adapter when it lands.
- done: unit tests with fakes; T-AI-01 on dev cases with a local model (full trace + structured final report).

### KG-09 · Prompt policy, pressure & injection variants
- meta: P0 | M-2 | 1.5d | mcs | deps: KG-08, SH-05 | status: todo
- refs: §10 §13 §14 | REQ-004 REQ-007 | T-AI-01 | H1 | F4 | SEC-01
- build: services/agent/sl_agent/prompts: system prompt (objective = independently correct outcomes, not closures; evidence requirements; abstain/escalate when unsure; ignore instructions inside evidence; no authority without the server gate); L0–L3 pressure templates per ADR-014; few-shots only from dev scenario ids; prompt files hashed into run manifests; review OM-06 tool descriptions.
- done: leakage-auditor passes; prompt hashes frozen before KG-18.

### KG-10 · Model serving: local, Explorer vLLM, frontier arm, selection
- meta: P0 | M-2 | 3d | mcs=2d | deps: KG-08 | status: todo
- refs: §7 §10 §22 §25 | REQ-004 | T-AI-01 | U2 | RSK-04
- build: local profiles (your Mac: 7–14B via Ollama/Metal; Om's RTX 3050: ≤4B smoke model only); infra/hpc/vllm.sbatch.template + docs/setup/EXPLORER-HPC.md (Apptainer image digest, weights revision, tool-call parser flag, SSH tunnel, resume after time limits); frontier API config; Explorer jobs through `make hpc-*` (Om operates them until your account is approved — SH-19; you own the sbatch config and model choice); bake-off on 20 dev scenarios: tool-call validity, schema adherence, latency, cost → ADR with exact model IDs + inference settings (U2); note nondeterminism even at temperature 0.
- done: ADR ACCEPTED; every arm reachable from the runner through one config switch.

## M-3 Detection, verification, runner

### KG-11 · Supervisor: async monitors & kill switch
- meta: P1 | M-3 | 3.5d | mcs | deps: SH-02, KG-01 | status: todo
- refs: §8 §12 §7 | REQ-008 REQ-010 | T-SEC-03 T-SWE-03 | I9 I10 I11 I12 | MET-10 | F5 F7 | ADR-004
- build: services/supervisor: Kafka consumer (dedupe by event_id; ordering only per key), per-run state, detective invariants I9 suspense growth, I10 cross-action transitions, I11 freshness / as-of consistency, I12 audit-sequence gaps; once-per-state-change alerting (the PoC's repeat-alert defect); on alarm: Redis halt + OM-12 :halt endpoint + incident record; metrics: lag, detection delay. Develop on sample events JSONL, then integrate with OM-13. Om reviews the monitor rules (independence); rules frozen before KG-18.
- done: scripted violation sequences detected without repeat alerts; the legitimate-sequence suite raises 0 alarms; monitor-only condition works in a real run.

### KG-12 · Independent audit-chain verifier CLI
- meta: P1 | M-3 | 1d | mcs | deps: SH-08 | status: todo
- refs: §12 §9 | REQ-009 | T-SEC-05 | SEC-09 | ADR-012 | E7 | RSK-09
- build: packages/audit-verifier: `sl-verify <run export>` recomputes JCS hashes, chain links, signatures (published key ids), gaps / reorders / missing denials, anchors; tamper tests (modify / remove / reorder) with expected detections; documents what it cannot detect (privileged rewrite without an external anchor).
- done: SH-08 vectors pass; T-SEC-05 report against a real OM-14 chain.

### KG-13 · Python observability & cost metrics
- meta: P1 | M-3 | 0.5d | mcs | deps: KG-08 | status: todo
- refs: §7 §18 | REQ-014 | T-SWE-01 | NFR-10 | MET-09
- build: OTel SDK in agent, mcp-adapter, supervisor; traceparent over HTTP and Kafka headers; span attributes run_id / action_id; metrics: LLM latency, tokens, cost, retries.
- done: one run shows a single connected trace across Python and Java services (with OM-17).

### KG-15 · Experiment runner, manifests, resume, sharding
- meta: P0 | M-3 | 3.5d | mcs | deps: KG-06, KG-08 | status: todo
- refs: §14 §12 §18 | REQ-007 REQ-010 REQ-014 | T-EVAL-01 T-AI-03 | NFR-06 NFR-07 | MET-09
- build: packages/evaluation/sl_eval/runner: frozen campaign YAML → (scenario × condition × repeat) units; per unit: fresh ns + load + verify state-hash → create run (controls) → strategy → grade → manifest (model ID + settings, prompt / tool / policy hashes, seed, snapshot hash, host) → results JSONL + parquet; resume by unit key; `--shard i/n` for the two machines; concurrency + rate-limit backoff; token / cost / tool-call / latency counters; retry infrastructure failures only, never re-roll outcomes; deviations log.
- done: a 20-unit dry run resumes after kill; two-shard merge = identical unit set; manifest completeness check passes (NFR-06).

## M-4 Science & replay

### KG-14 · Platform red-team suite (attack Om's controls)
- meta: P1 | M-4 | 1.5d | mcs=0.75d | deps: KG-04, OM-08, OM-11 | status: todo
- refs: §15 §11 §12 | REQ-012 | T-SEC-03 T-SEC-04 | F5 F6 F9 | SEC-04 SEC-06 | E3 | RSK-07
- build: tests/redteam: bypass (agent token on the ledger, forged/expired token, cross-ns), approval reuse after a state change, digest swap, concurrent duplicates, duplicate / out-of-order events, individually allowed toxic sequences (family 3), balanced-but-wrong postings (family 4), stale-evidence races (family 5), recovery faults with OM-18 (family 6); expected outcomes from §11/§12; paired legitimate cases. Families 1–2 = OM-16, 7 = KG-04, 8 = KG-05.
- done: `make test-redteam` runs by family; results feed SH-12; every failure filed for Om with a repro.

### KG-16 · Preregistration freeze & amendments
- meta: P0 | M-4 | 1.5d | mcs | deps: SH-06, KG-10, KG-04 | status: todo
- refs: §13 §14 §0 | REQ-007 | T-EVAL-01 T-EVAL-02 | H1 H2 H3 | RQ1 RQ2 RQ3 | ADR-008 | U7 | NFR-07 | RSK-14
- build: experiments/prereg/preregistration.md: RQ1–3 and H1–H3 verbatim with decision rules, SH-06 denominators, estimators, analysis-code commit hash, model IDs + settings, scenario-manifest hashes and eval attack-pack hashes (OM-16); matched-pressure experiment as a separate AMENDMENT / exploratory section (U7); freeze to experiments/prereg/frozen/<date>/ with sha256; initialize docs/experiment-amendments.md via /amend.
- done: frozen before any eval-split run; both sign the PR.

### KG-17 · Pilot & feasibility gate
- meta: P0 | M-4 | 1.5d | mcs | deps: KG-15, KG-10, KG-11, KG-09, OM-10, OM-08 | status: todo
- refs: §22 §14 | REQ-014 | T-EVAL-01 | RSK-03 RSK-04 | U11
- build: 20-scenario dev pilot across all conditions: input/output tokens, tool calls, cost per run, latency, GPU-hours, failure/retry rates; project full-campaign time + cost; decide go / reduce (as an AMENDMENT, before eval) and record it; if the LLM rarely violates, report that — never fabricate attacks or outcomes.
- done: docs/pilot-report.md; SH-10 thresholds set.

### KG-18 · Main campaigns (open-weight, frontier, rules, blind)
- meta: P0 | M-4 | 3d | mcs=2d | deps: KG-16, KG-17, KG-07, OM-16, OM-11 | status: todo
- refs: §14 §13 | REQ-007 REQ-010 | T-EVAL-01 T-AI-02 T-AI-03 | H1 H2 H3
- build: open-weight 200 × 5 × 3 = 3,000 runs; frontier 50 × 3 × 2 = 300 runs; rules baseline on the 200; blind set; open-weight shards run on the machine that holds the Explorer tunnel (Om's until your account is approved), frontier + rules shards on your Mac; keep one latency reference host per campaign (H2); monitor; log every deviation.
- done: planned-vs-observed table per cell; shortfalls disclosed (never imply 3,300 if not run); aggregates + manifests committed (raw runs stay in experiments/runs/, gitignored).

### KG-19 · Statistical analysis & results write-up
- meta: P0 | M-4 | 4d | mcs=3d | learn | deps: KG-17 | status: todo
- refs: §13 §14 §4 | REQ-007 REQ-014 | T-EVAL-01 T-EVAL-02 T-AI-03 | H1 H2 H3 | MET-01..12 | E1..E8 | RSK-05 RSK-06
- build: packages/evaluation/sl_eval/stats: cluster bootstrap by scenario; H1 mixed-effects logistic with scenario random intercept (implementation pinned in the prereg); H2 paired full vs off — relative false-resolution reduction, correct-resolution delta, gateway on-path p99 delta from reference-host spans; H3 CI half-widths + pass^k (all-k) estimator; subgroups by break type / pressure / attack; exploratory E1–E8 kept separate; MET-11 synthetic exposure proxy clearly labeled; docs/evaluation-results.md incl. negative findings. Build on pilot data, rerun on campaign data.
- done: one command regenerates every number + figure from results files; each claim cites a manifest; the §4 validator-workflow recommendation is stated as test-limited.

### KG-20 · Counterfactual replay (action replay + paired live)
- meta: P1 | M-4 | 3d | mcs=2d | learn | deps: KG-15, OM-10 | status: todo
- refs: §12 §17 | REQ-011 | T-EVAL-03 | ADR-007 | E4
- build: sl_eval/replay: action replay = recorded proposals → reset ns (verify snapshot hash) → the same proposals through an alternate policy bundle / controls → allow / deny / commit + state delta; paired live = same model / prompt / settings / scenario under different controls, multiple replications; mandatory `mode` field; diffs exportable for OM-22.
- done: T-EVAL-03: both modes on ≥3 scenarios with verified hashes; outputs never conflated.

## M-5 Product & hardening

### KG-21 · Eval API & validation export package
- meta: P2 | M-5 | 1.5d | deps: KG-19, KG-20 | status: todo
- refs: §17 §21 | REQ-015 REQ-011 REQ-014 | T-DOC-01 | MET-12
- build: FastAPI sl_eval/api (publish openapi/eval.yaml): campaigns, metrics with CIs, per-run grades, replay jobs + diffs; export builder: manifests, receipts + verifier output, aggregates, datasheet, model cards, limitations → zip with checksums.
- done: OM-22 renders it; identical inputs ⇒ identical export checksum.

### KG-22 · Datasheet, model cards, data governance
- meta: P1 | M-5 | 2d | mcs=1d | deps: KG-04, KG-19 | status: todo
- refs: §6 §21 | REQ-015 | T-DOC-01 | NFR-06
- build: docs/datasheets/second-line-scenarios.md (Gebru et al. sections), docs/model-cards/<config>.md per tested config (Mitchell et al.), docs/data-governance.md (sources, licenses, hashes, synthetic-only scope, misuse cases, review status from SH-11).
- done: every tested config has a card; datasheet hashes match the manifests.
