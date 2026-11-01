# services/ledger — financial authority (owner: Om)
Spring Boot · Java 21 · PostgreSQL 17 via Flyway · Testcontainers. The ONLY component that mutates financial state (ADR-002).

## Layout (keep updated — part of DoD). Built = OM-03 + OM-04; the rest is planned.
```text
com.secondline.ledger
  LedgerException  typed failure (contracts ErrorCode; grader-only codes refused); nothing was written
  domain/        Money Quantity Price FxRate Isin Currency CashAccount SecuritiesAccount (BigDecimal only;
                 extra scale rejected, never rounded; ArchUnit bans float/double)            [built]
  journal/       CashPostingService (Σ D = Σ C per currency), SecuritiesPostingService (per ISIN),
                 ReversalService (full negation + reason, one per entry), JournalRepository   [built]
  positions/     PositionProjection: from securities_lines only; stored == recompute         [built]
  ns/            NamespaceRepository: EMPTY → LOADED → RETIRED, bumpVersion, requireLoaded  [built]
  load/          BundleGuard (truth keys, canaries, B1–B8 labels, schema, refs; pure) ·
                 WorldBundleLoader (one tx, idempotent by bundle hash) · TruthKeys          [built]
  export/        NamespaceExporter (ns_export, schema-checked) · StateHash (JCS without ns)  [built]
  read/          ReadService + ReadController: the 11 §10 read tools, as-of versions        [built]
  admin/         AdminController: create / :load / export / state-hash / retire / runs      [built]
  web/           ErrorAdvice: every error is a contracts error_response                    [built]
  verify/        pre-commit validators, one per action type (§8 step 5)
  approvals/     maker-checker bound to ActionDigest (ADR-011)
  idempotency/   UNIQUE(actor_scope, operation_type, key) + payload digest
  outbox/ receipts/   same-transaction outbox; per-run receipt hash chain
  api/internal   gateway service JWT only · api/admin operator · api/review humans
  security/      one filter chain per realm
resources/db/migration/   V###__*.sql (.claude/rules/migrations.md)
  V001 namespaces · V002 domains + reference data · V003 operational records · V004 two ledgers,
  deferred balance triggers (P0002 cash / P0003 securities), immutability triggers (P0001), positions ·
  V005 ns lifecycle + write-once snapshot, committed_version stamped by trigger, refs, evidence/break
  columns, agent_runs, canary CHECKs
```
## DB roles (ADR-019)
`ledger_migrator` owns schema `ledger`; Flyway runs only in the one-shot `ledger-migrate` compose service
(profile `migrate`). The running ledger is `ledger_svc` (role `ledger_app`): SELECT/INSERT everywhere,
UPDATE only on `breaks(status, state_version)`, `positions` and `namespaces(snapshot_id, status, loaded_at,
state_version)` (guarded by trigger), never DELETE/CREATE. Retiring a namespace keeps its rows (ADR-019 Addendum A). Tests use
`LedgerDb` (one Testcontainers Postgres initialised with the shipped `infra/db/init`), `Services` (real
services + standalone MockMvc for the read/admin routes) and `Bundles` (the contracts WorldBundle example).
## Commands
`make test-ledger` (Testcontainers; ~5 min incl. the jqwik properties) · `make test-int` · `./gradlew :services:ledger:bootRun`
## Conventions
- Write path = validate → approval/idempotency → ONE @Transactional commit (domain change + receipt + outbox) → typed result. Errors only from the contracts ErrorCode enum.
- Test names carry spec IDs: `T_SWE_02_concurrentDuplicatesHaveOneEffect`, `T_DOM_01_…`.
- Testcontainers singleton containers (one Postgres/Kafka per test JVM) — Om's laptop has 16 GB. Local runs -Xmx512m, Gradle workers ≤ 4.
- Read first: §5 §8 §9 §12 shards; ADR-015/016/017.
