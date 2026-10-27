# Om Patel — board (Authority & Platform)

Owner key `om`. Claude reads this through `python3 scripts/board.py next` (prints only the cards it needs) — keep the card format exact.
**Role:** CI/CD owner — approves and merges every PR (`/review-pr <n>`); holds the Explorer HPC account (SH-19).
**Scope:** everything that AUTHORIZES, VALIDATES, COMMITS and RECORDS — ledger, gateway, MCP adapter (tool surface), OPA, budgets/halts, outbox→Kafka, receipts, secrets hygiene, observability, chaos/load, review API, console, demo env, plus agent-facing attack packs (you attack Kunal's agent; Kunal red-teams your controls).
**Machine:** ASUS Vivobook Pro 15 OLED — Ryzen 7 5800H (8C/16T), 16 GB RAM, RTX 3050 Laptop (4 GB VRAM). Work inside WSL2 (`docs/setup/OM-windows-wsl.md`). Give WSL ≤10 GB, start compose profiles selectively, JVMs at -Xmx512m. GPU = ≤4B smoke-test models only, never an experiment arm.
**Legend:** `meta` = priority | milestone | estimate (focused days, no AI assist) | `mcs` in minimum credible scope (`mcs=Xd` reduced) | `learn` interview-critical | `skills:` task skills the card requires (gate-checked) | deps (needed to START; integration lives in `done`) | status.

## M-0 Contracts & setup

### OM-01 · Monorepo bootstrap, Compose base, CI skeleton
- meta: P0 | M-0 | 2d | mcs | deps: SH-01 | status: todo
- refs: §7 §19 §21 | NFR-11 NFR-06 | T-DOC-01 | ADR-009 ADR-010 | RSK-12
- build: dirs from the CLAUDE.md repo map. Gradle Kotlin DSL multi-project (services/ledger, services/gateway, libs/contracts-java) + gradle/libs.versions.toml: Java 21, Spring Boot 3.5.x pinned (4.0.x only via ADR; default chosen for Jackson-2 library compatibility). infra/compose/docker-compose.yml profiles: core (postgres 17, redis 7, opa 1.x) · app (ledger, gateway, mcp-adapter) · events (kafka KRaft, supervisor) · obs (otel-collector, jaeger, prometheus, grafana) · ui (console) · chaos (toxiproxy); healthchecks; mem_limit per service sized for a 16 GB host; multi-stage Dockerfiles so the teammate needs no JDK; multi-arch base images (Kunal is arm64). infra/db/init/00-roles.sql: schemas ledger, audit, eval; roles ledger_app, grader_ro, operator. Replace Makefile TODO stubs: bootstrap up down ps logs reset db-shell lint test codegen. GitHub Actions: path-filtered java / python / policy / console jobs next to kit-checks; Testcontainers-ready. pre-commit: gitleaks, LF, EOF. No Kubernetes.
- done: fresh clone on BOTH machines: `make bootstrap && make up PROFILES="core"` healthy in < 2 min; CI green; `make ctx` under budget; infra/CLAUDE.md lists the real commands.

### OM-25 · CI/CD ownership: rulesets, required checks, PR automation
- meta: P0 | M-0 | 2d | mcs=1d | deps: SH-01 | status: todo
- refs: §19 §21 §23 | NFR-07 NFR-11 | T-DOC-01 | ADR-010 | RSK-01 RSK-14
- build: on omunite215/Project_SecondLine per docs/setup/GITHUB.md: Kunal as collaborator (Write); squash-only merges + auto-delete branches; ruleset on main (PR + 1 approval + code-owner review + conversation resolution + required checks; no force-push/deletion; admin bypass only for Om's own PRs after green CI); `ai-review` label + .github/workflows/claude-review.yml with secret CLAUDE_CODE_OAUTH_TOKEN; required checks grow as services land (java, python, policy, console, leakage, contracts drift); CI caches (Gradle, uv, pnpm); Dependabot entries per ecosystem; tag each milestone gate (m0…m5); review every PR within 24 h with /review-pr.
- done: a test PR from Kunal cannot merge until CI is green and Om approves; Om's own PR merges only via bypass with green CI; claude-review posts on a labeled PR; GITHUB.md matches the real settings.

### OM-26 · Kit hardening: hpc.sh input, leakage hook, skills gate
- meta: P1 | M-0 | 0.5d | deps: SH-01 | status: todo
- refs: §11 §19 §21
- skills: insecure-defaults
- build: from the SH-01 automated security review. (1) scripts/hpc.sh: reject non-numeric `TAIL` and job ids before they reach the remote command. (2) .claude/hooks/guard_edit.py: scan `new_string` in every `tool_input.edits[]` entry; block unrecognised edit shapes; anchor the test-path exemption to real test dirs/suffixes. (3) scripts/skills.py BASH_OK: reject newlines, `$(`, backticks, redirects and `&` (or shlex-parse against an exact allowlist). (4) scripts/skills.py EDIT_ALLOW: drop .claude/ and tooling/ (the guardrails), and add `Edit(...)` ask rules for them in .claude/settings.json (ask, not deny: the human approves each guardrail edit, Claude can still maintain the kit). (5) PR #1 review: cut cards don't cover spec IDs; `summary --write` and `set` fail loudly instead of no-op success; plugins must come from the manifest's marketplace; unpinned vendored skills and corrupt locks are RED; `skills.py install` needs approval (narrowed `python3 scripts/*` allow + skills' allowed-tools); `make trace-check` in kit-check (CI parity); claude-review runs on `pull_request_target`, only when Om labels, with the token as a `claude-review` environment secret limited to `main` (env required-reviewers need Enterprise on private repos; branch policies don't). Suites (tests/security, tests/kit) run in `make kit-check` and CI.
- done: one failing-first test per item under tests/security/ (OM_26_*): TAIL injection rejected; multi-edit truth wiring blocked; each bypass string rejected by the RED gate; gate-RED edits to settings/hooks/manifest blocked; `make kit-check` green.

## M-1 Truthful simulator (ledger side)

### OM-02 · Java contracts library (types, schema validation, JCS, digests)
- meta: P0 | M-1 | 1d | mcs | deps: SH-02 | status: todo
- refs: §9 | ADR-005 ADR-011 | REQ-005
- build: libs/contracts-java: types generated from packages/contracts (jsonschema2pojo task) or records + a generator check; networknt JSON-Schema validator with cached schemas; ErrorCode enum generated from errors.json; CanonicalJson (RFC 8785 / JCS) + Digests.sha256; ActionDigest(action, evidence versions, state_version) shared by approvals and idempotency.
- done: every §9 example validates; JCS matches SH-08 vectors once they exist; `make codegen` deterministic (CI fails on diff).

### OM-03 · Ledger core: schema, journal, positions, immutability
- meta: P0 | M-1 | 4d | mcs | deps: OM-01, OM-02, SH-03 | status: todo
- refs: §5 §9 | REQ-002 | T-DOM-01 T-DOM-05 | I1 I2 | ADR-002 | NFR-02 | SEC-12
- build: Flyway V001+: institutions, counterparties, instruments, trades, bookings, allocations, settlement_instructions, settlement_events, custodian_records, positions (projection), cash_accounts, journal_headers/journal_lines (NUMERIC + CHAR(3) currency), reference_data_versions, corporate_actions, fx_snapshots, evidence_records, breaks (state_version); every table keyed (ns, id). PostingService enforces Σdebit = Σcredit per currency inside the transaction; trigger blocks UPDATE/DELETE of committed journal rows; corrections = reversing entry with reverses_id; quantity/position changes are domain transactions, never cash entries; ArchUnit rule bans float/double in domain packages.
- done: jqwik property tests T-DOM-01 (valid postings stay balanced, unbalanced rejected, per-currency precision); T-DOM-05 reversal keeps the original row; migrations apply cleanly in CI on Testcontainers.

### OM-04 · Ledger reads, scenario loader, namespaces, export & state hash
- meta: P0 | M-1 | 3d | mcs | deps: OM-03 | status: todo
- refs: §5 §9 §12 | REQ-001 REQ-002 REQ-011 | T-EVAL-03 T-DOM-03 | ADR-007 ADR-015
- build: /internal/v1/ns/{ns}/… read endpoints backing every §10 read tool (as-of params, record versions, provenance); /admin/v1/ns (create), …/{ns}:load (WorldBundle → rows, idempotent by bundle hash, rejects any truth-schema field), …/export (canonical JSON), …/state-hash (sha256 of the JCS export), DELETE; agent_runs registry (run_id, ns, controls, manifest_ref).
- done: load → export → hash identical across two loads and both machines; a bundle containing a truth field is rejected; read endpoints contract-tested against openapi/ledger-internal.yaml; KG-06 consumes the export.

## M-2 Real agent (tool boundary)

### OM-05 · Gateway: REST tool API, run tokens, OPA hook, decision log
- meta: P0 | M-2 | 4d | mcs | learn | deps: OM-02, SH-05 | status: todo
- refs: §7 §8 §10 §11 | REQ-004 REQ-005 REQ-016 | T-SEC-02 | ADR-005 ADR-013 | SEC-03 | NFR-08 | MET-09 | RSK-05
- skills: insecure-defaults
- build: services/gateway (Spring Boot): POST /v1/runs (operator auth) → ns-bound run + short-lived Ed25519 JWT (aud, sub, run_id, ns, scenario_id, allowed_tools, controls, exp); POST /v1/runs/{runId}/tools/{tool} → verify token + run binding → JSON-Schema input check → budget/halt check → OPA query (per ADR-014 condition) → route to ledger with the gateway service JWT → typed result/error; every decision incl. denies persisted via ledger /internal/v1/decisions; Micrometer histogram `gateway.onpath` (fine p99 buckets) + OTel span with run_id/action_id; writes fail closed if OPA or ledger is unreachable. Stub the ledger until OM-04 lands.
- done: contract tests vs openapi/gateway-tools.yaml; a denied call leaves the ledger state-hash unchanged; OPA down ⇒ writes denied with a typed error; on-path p50/p95/p99 logged locally (measured, not claimed).

### OM-06 · MCP adapter: thin, unprivileged tool surface
- meta: P0 | M-2 | 1.5d | mcs | deps: SH-02, KG-01 | status: todo
- refs: §10 §11 §24 | REQ-004 | T-AI-01 | ADR-005 ADR-013 | U3 | SEC-01
- skills: mcp-server-dev
- build: services/mcp-adapter (Python, official MCP SDK pinned to the spec revision in ADR-013), Streamable HTTP; one MCP tool per §10 tool, generated from packages/contracts/tools schemas; LLM-facing descriptions in services/mcp-adapter/descriptions/*.md (Kunal reviews: they shape agent behavior); forwards Authorization bearer + traceparent to the gateway; holds no credentials, state or policy; evidence text returned only in `untrusted_text` fields, never merged into descriptions or error messages; none of the §10 NOT-exposed capabilities exist. Test against a Prism mock of gateway-tools.yaml until OM-05 lands.
- done: MCP Inspector lists exactly the §10 tools; contract tests pass against the mock, then the real gateway; the adapter container cannot reach Postgres/OPA/Redis (compose network test).

## M-3 Safety boundary

### OM-07 · Ledger trust boundary: auth realms & bypass test
- meta: P0 | M-3 | 1d | mcs | deps: OM-04, OM-05 | status: todo
- refs: §11 §8 | REQ-016 REQ-005 | T-SEC-01 | SEC-02 | F9 | NFR-04
- skills: insecure-defaults
- build: Spring Security filter chains: /internal/** accepts only the gateway service JWT (aud=ledger); /admin/** operator credential; /review/** human users (OM-20); agent run tokens rejected on every ledger route; ns scope taken from token claims and checked against the path.
- done: T-SEC-01: agent token ⇒ 401/403 on all write routes with state-hash unchanged; cross-ns read/write denied; tests named T_SEC_01_*.

### OM-08 · Pre-commit verifier & domain write transactions
- meta: P0 | M-3 | 4d | mcs | learn | deps: OM-04, SH-04 | status: todo
- refs: §8 §5 §9 | REQ-005 REQ-002 | T-DOM-04 T-SEC-02 | I3 I4 I5 I6 I7 I8 | F2 F3 | SEC-05 | ADR-004 | NFR-01
- build: services/ledger/…/verify: one validator + @Transactional handler per action type (classification, booking correction, corporate action, adjustment, escalation): evidence ids exist, belong to the break and match the cited version; currency/amount/quantity precision; permitted source/target accounts; no reference-data mutation; closure needs supporting state (I5); B7/B8 escalate-only (I6); expected_state_version (I7); approval-digest (OM-11) and idempotency (OM-09) hooks. Any failure ⇒ typed error and zero mutation; success ⇒ domain change + receipt + outbox row in ONE transaction. Condition-specific behavior from ADR-014.
- done: unit test per validator; integration: stale evidence ⇒ EVIDENCE_STALE with state-hash unchanged; reference-data write attempt denied; the known balanced-but-wrong case is blocked OR listed as an oracle-only gap per SH-04 (T-DOM-04 reports the actual outcome).

### OM-09 · Idempotency & concurrency control
- meta: P0 | M-3 | 2d | mcs | learn | deps: OM-08 | status: todo
- refs: §8 §9 | REQ-005 | T-SWE-02 | I8 | SEC-07 | ADR-011 | F6 F7 | NFR-01
- build: idempotency_records UNIQUE(actor_scope, operation_type, idempotency_key) + payload digest; same key + same digest ⇒ stored prior result; same key + different digest ⇒ IDEMPOTENCY_CONFLICT; optimistic state_version on breaks + SELECT … FOR UPDATE where needed; write down the chosen isolation level and why (ADR note).
- done: T-SWE-02: 20 concurrent identical requests ⇒ exactly one business effect and identical responses; mixed payloads ⇒ conflicts; runs on Testcontainers Postgres in CI.

### OM-10 · OPA policy bundle (Rego v1) & policy tests
- meta: P0 | M-3 | 2.5d | mcs | deps: OM-05, SH-05 | status: todo
- refs: §11 §8 §10 | REQ-005 REQ-010 | T-SEC-02 | SEC-03 SEC-04 | F1 F2 | I4 I9 | RSK-07
- skills: insecure-defaults
- build: infra/opa/policies: default deny; decisions allow | deny | requires_review with reason codes; role/action matrix, per-break-type allowed actions, posting limits, permitted + suspense accounts, reference-data immutability, approval thresholds, toxic sequences (input carries the run's recent actions); bundle revision + hash returned in every decision; numbers come from SH-05, never invented.
- done: `make test-policy` (opa test, ≥1 test per rule incl. default-deny) in CI; decisions carry the bundle hash; T-SEC-02 negative cases pass end-to-end through the gateway; hard legitimate cases still allowed (no block-everything).

### OM-11 · Maker-checker approvals bound to the action digest
- meta: P0 | M-3 | 2d | mcs | learn | deps: OM-08 | status: todo
- refs: §8 §17 | REQ-005 REQ-013 | T-SEC-04 T-UI-01 | ADR-011 | SEC-06 SEC-10 | I7 | F6
- build: approval_requests / approval_decisions (immutable); digest = sha256(JCS(action + evidence versions + state_version)); expiry; checker ≠ maker; reason code required; any change ⇒ new approval; REVIEW_REQUIRED response carries approval_id; agent polls get_approval_status; endpoints used by OM-20/OM-21.
- done: T-SEC-04: expired approval, changed payload or bumped state_version ⇒ no commit (APPROVAL_EXPIRED / STATE_CONFLICT); same-identity approval rejected.

### OM-12 · Run budgets, halt flags, degraded mode
- meta: P1 | M-3 | 1.5d | mcs | deps: OM-05 | status: todo
- refs: §11 §8 | REQ-008 | T-SEC-07 | SEC-13 | U11 | F9
- build: Redis per-run counters (tool calls, wall time, cost units) + advisory halt:{run}; durable agent_runs.status checked inside the ledger commit transaction (authoritative); POST /internal/v1/runs/{id}:halt for the supervisor (service auth); monitor-degraded state when Kafka/supervisor is down restricts supervision-dependent actions (ADR-014). Limits from SH-10.
- done: T-SEC-07: budget exceeded or halt ⇒ later calls RUN_HALTED; Redis down ⇒ the durable check still blocks; docs state that halts never undo earlier commits.

### OM-13 · Transactional outbox & Kafka relay
- meta: P1 | M-3 | 2d | mcs | learn | deps: OM-08 | status: todo
- refs: §12 §7 | REQ-008 | T-SWE-03 T-SWE-01 | SEC-08 | F7 | ADR-004 | NFR-03 | RSK-08
- build: outbox row (§12 envelope fields + traceparent) in the same transaction as every committed change and every receipt; relay = scheduled poller with FOR UPDATE SKIP LOCKED, publish keyed by run_id to `ledger.events`, mark published, retry with backoff; metrics: backlog size, oldest-unpublished age.
- done: T-SWE-03: kill the relay between commit and publish ⇒ after restart every event_id is published (duplicates allowed, deduped downstream); Testcontainers Kafka integration green; KG-11 consumes the topic.

### OM-14 · Decision receipts: hash chain, signatures, checkpoints
- meta: P1 | M-3 | 2d | mcs=1d | learn | deps: OM-08 | status: todo
- refs: §9 §12 | REQ-009 | T-SEC-05 | ADR-012 | SEC-09 | F9 | NFR-05 | RSK-09
- build: audit_receipts with a single serialized writer per run; one receipt per §9 for ALLOW / DENY / REVIEW_REQUIRED / EXECUTED (denials are first-class); previous_receipt_hash chain; JCS + sha256; Ed25519 detached signature with key id (key file path from env, never in the repo); periodic checkpoint export (head hash + signature) to experiments/anchors/. Implements SH-09. MCS: unsigned chain + checkpoints, signatures later.
- done: SH-08 vectors pass; KG-12 verifies a real run's chain and reports tamper detections.

### OM-15 · Secrets hygiene & log/trace redaction
- meta: P1 | M-3 | 1d | mcs=0.5d | deps: OM-05 | status: todo
- refs: §11 §6 | REQ-016 | T-SEC-06 | SEC-11 SEC-14 | NFR-04
- skills: insecure-defaults
- build: gitleaks in pre-commit + CI; structured-log redaction of Authorization headers, tokens and keys; span-attribute allowlist (no truth fields, no secrets); only .env.example committed; fixture/snapshot hashes verified on load (SEC-14 provenance).
- done: CI fails on a planted test secret; log + trace scan of a full run finds no tokens; a tampered fixture hash is rejected.

### OM-16 · Agent-facing attack packs (prompt injection, temptations)
- meta: P0 | M-3 | 1.5d | mcs=1d | deps: SH-02, SH-05 | status: todo
- refs: §15 §6 §11 §3 | REQ-012 | T-SEC-06 | F1 F4 | SEC-01 | E3 | RSK-03
- build: data/attacks/{dev,eval}/*.yaml per the contracts attack_pack schema: family 1 (reward-hacking temptations: suspense-plug hints, "just close it" pressure) and family 2 (indirect injection in memo / email / status text: ignore policy, fake approval, privileged tool request). Per payload: placement, target break types, expected safe behavior, severity, provenance (original | adapted from AgentDojo / InjecAgent with citation + license note, no bulk copying); paired benign look-alikes (urgent but legitimate) so block-everything can't win. Held-out eval packs stay unseen by Kunal's tooling (his local settings deny-read data/attacks/eval/**) — this is what makes the injection evaluation independent.
- done: KG-04 applies the dev packs to injection=yes variants; eval packs frozen before KG-16; attacks ship only with mitigations (ethics note).

## M-5 Product & hardening

### OM-17 · Observability stack & dashboards
- meta: P1 | M-5 | 2d | mcs=0.5d | deps: OM-05, OM-13 | status: todo
- refs: §7 §17 §18 | REQ-014 | T-SWE-01 | NFR-10 | MET-09 MET-10
- build: OTel Java agent on ledger + gateway; infra/observability/otel-collector.yaml → Jaeger (traces) + Prometheus; Grafana provisioned dashboards: gateway on-path p50/p95/p99 by tool × controls, deny rate by reason, approvals pending, outbox backlog/age, consumer lag + detection delay (KG-11/KG-13 metrics), halts; trace attributes run_id / action_id / tx_id. MCS: Jaeger + one dashboard.
- done: one run traceable agent → mcp → gateway → ledger → outbox → supervisor in Jaeger; dashboards load from provisioning on a fresh `make up PROFILES="core app obs"`.

### OM-18 · Chaos & fault-injection matrix
- meta: P1 | M-5 | 2.5d | mcs=1d | deps: OM-13, OM-12, OM-10 | status: todo
- refs: §12 §11 §15 | REQ-012 | T-SWE-05 T-SWE-01 | E5 | NFR-03 | SEC-08 | RSK-08
- build: infra/toxiproxy + tests/chaos: every §12 chaos-matrix row with its expected allowed / denied / recovery state — restart between commit and publish, duplicate publish, consumer outage/backlog, delayed/reordered events, Redis outage, OPA outage, approval expiry, version race, concurrent duplicates, gateway↔ledger partition, invalid tool schema, UI disconnect, kill switch after a commit (model-timeout row belongs to KG-08). Results in docs/chaos-results.md. MCS: commit/publish restart, OPA down, Redis down, duplicate submit.
- done: every row executed with an outcome (pass / fail / known gap); high-risk writes fail closed; reruns scripted via `make test-chaos`.

### OM-19 · Load test (k6, up to 50 concurrent runs)
- meta: P1 | M-5 | 1.5d | mcs=0.5d | deps: OM-09 | status: todo
- refs: §18 §14 | REQ-014 | T-SWE-04 | NFR-08 NFR-09 | MET-09 | H2
- build: infra/k6: replay recorded tool-call mixes (KG-15 action logs or scripted policies) across up to 50 namespaces in parallel, per controls mode; capture p95/p99 + host specs; run on both laptops and report separately (laptop numbers are not SLAs).
- done: docs/load-results.md with environment, concurrency, numbers and limits; no SLA language.

### OM-20 · Review API (approvals, runs, live updates)
- meta: P1 | M-5 | 2d | mcs=1d | deps: OM-11, OM-14 | status: todo
- refs: §17 §8 §4 | REQ-013 | T-UI-01 | SEC-10
- build: ledger /review/v1: breaks, runs, actions, decisions, receipts (paginated); approve/reject (checker role, reason code, digest echo); SSE /review/v1/runs/{id}/events; local synthetic users maker / checker / validator / engineer with dev JWT login; publish openapi/review.yaml.
- done: API tests incl. maker = checker rejection; SSE delivers run events in < 1 s locally.

### OM-21 · Console core: break queue, approvals, run trace
- meta: P1 | M-5 | 4d | mcs=2d | deps: OM-20 | status: todo
- refs: §17 §4 | REQ-013 | T-UI-01 | NFR-12 | SEC-10
- skills: frontend-design
- build: apps/console (Next.js + TypeScript, typed clients via openapi-typescript): role-aware login; Operations break queue (filters status / type / severity / as-of; internal vs custodian evidence side by side); approval inbox (evidence refs + versions, proposed vs resulting state delta, digest, mandatory reason code, maker/checker shown); run-trace timeline (proposal → policy → approval → commit/deny → outbox → monitor → receipt → grade) with SIMULATED / SCRIPTED / REAL LLM RUN labels; SSE with polling fallback; keyboard navigation. MCS: approval inbox + run trace.
- done: Playwright T-UI-01: approval needs a reason code; maker ≠ checker enforced server-side; decision stored.

### OM-22 · Console: Counterfactual Lab, Validation, Evidence Export
- meta: P2 | M-5 | 3d | deps: OM-21 | status: todo
- refs: §17 | REQ-011 REQ-014 REQ-015 | T-EVAL-03 | MET-12
- skills: frontend-design
- build: Lab: choose run → action replay vs paired live (explicit mode label) → side-by-side timelines + state diff from KG-21; Validation: campaign selector, metrics with CIs, H1–H3 status (supported / rejected / inconclusive), safe-automation-vs-risk frontier; Export: download the validation package + chain-verification status. Build against an openapi/eval.yaml mock until KG-21 lands. Never show illustrative numbers as results.
- done: views render real campaign data with provenance labels; the Lab never conflates the two replay modes.

### OM-23 · Demo environment & fallback
- meta: P0 | M-5 | 1.5d | mcs | deps: OM-21, SH-07 | status: todo
- refs: §17 | T-UI-02 | RSK-13 | NFR-11 | REQ-013 | ADR-009
- build: make demo-up / demo-seed / demo-run / demo-test; seeded dev cases: one legitimate success with approval, one unsafe proposal blocked, one correct escalation; deterministic reset; endpoint prewarm; clearly labeled recorded-trace playback for no-network fallback; nothing depends on Explorer queues.
- done: clean clone → demo in ≤ 10 min on the demo machine; demo-test green twice in a row.

### OM-24 · Architecture, threat model & runbooks
- meta: P1 | M-5 | 1.5d | mcs=0.75d | deps: OM-18 | status: todo
- refs: §7 §11 §12 §21 | REQ-015 | T-DOC-01 | SEC-01..14 | NFR-05
- build: ARCHITECTURE.md (as-built diagram, trust boundaries, data flows, real-vs-stub table), docs/security-threat-model.md (SEC-01..14 → control → test → result), docs/runbooks.md (setup, reset, relay-crash recovery, key rotation, chaos reruns), OpenAPI links.
- done: every SEC row cites a test ID + outcome or an explicit gap; the claims rule passes.
