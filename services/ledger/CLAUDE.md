# services/ledger — financial authority (owner: Om)
Spring Boot · Java 21 · PostgreSQL 17 via Flyway · Testcontainers. The ONLY component that mutates financial state (ADR-002).

## Layout (keep updated — part of DoD). Built = OM-03; the rest is planned.
```text
com.secondline.ledger
  LedgerException  typed failure (errors.json code); nothing was written
  domain/        Money Quantity Price FxRate Isin Currency CashAccount SecuritiesAccount (BigDecimal only;
                 extra scale rejected, never rounded; ArchUnit bans float/double)            [built]
  journal/       CashPostingService (Σ D = Σ C per currency), SecuritiesPostingService (per ISIN),
                 ReversalService (full negation + reason, one per entry), JournalRepository   [built]
  positions/     PositionProjection: from securities_lines only; stored == recompute         [built]
  breaks/ evidence/ refdata/   read models with record versions + state_version
  verify/        pre-commit validators, one per action type (§8 step 5)
  approvals/     maker-checker bound to ActionDigest (ADR-011)
  idempotency/   UNIQUE(actor_scope, operation_type, key) + payload digest
  outbox/ receipts/   same-transaction outbox; per-run receipt hash chain
  ns/            namespace create / load / export / state-hash / delete (ADR-015)
  api/internal   gateway service JWT only · api/admin operator · api/review humans
  security/      one filter chain per realm
resources/db/migration/   V###__*.sql (.claude/rules/migrations.md)
  V001 namespaces · V002 domains + reference data · V003 operational records · V004 two ledgers,
  deferred balance triggers (P0002 cash / P0003 securities), immutability triggers (P0001), positions
```
## DB roles (ADR-019)
`ledger_migrator` owns schema `ledger`; Flyway runs only in the one-shot `ledger-migrate` compose service
(profile `migrate`). The running ledger is `ledger_svc` (role `ledger_app`): SELECT/INSERT everywhere,
UPDATE only on `breaks(status, state_version)` and `positions`, never DELETE/CREATE. Tests use
`LedgerDb` (one Testcontainers Postgres initialised with the shipped `infra/db/init`) and `Services`.
## Commands
`make test-ledger` (Testcontainers; ~5 min incl. the jqwik properties) · `make test-int` · `./gradlew :services:ledger:bootRun`
## Conventions
- Write path = validate → approval/idempotency → ONE @Transactional commit (domain change + receipt + outbox) → typed result. Errors only from the contracts ErrorCode enum.
- Test names carry spec IDs: `T_SWE_02_concurrentDuplicatesHaveOneEffect`, `T_DOM_01_…`.
- Testcontainers singleton containers (one Postgres/Kafka per test JVM) — Om's laptop has 16 GB. Local runs -Xmx512m, Gradle workers ≤ 4.
- Read first: §5 §8 §9 §12 shards; ADR-015/016/017.
