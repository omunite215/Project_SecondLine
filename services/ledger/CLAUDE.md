# services/ledger — financial authority (owner: Om)
Spring Boot · Java 21 · PostgreSQL 17 via Flyway · Testcontainers. The ONLY component that mutates financial state (ADR-002).

## Planned layout (keep updated — part of DoD)
```text
com.secondline.ledger
  domain/        Money, Quantity, Price, FxRate value objects (BigDecimal only)
  journal/       PostingService (Σ debit = Σ credit per currency), reversals
  positions/     projections from bookings + settlements (never cash journals)
  breaks/ evidence/ refdata/   read models with record versions + state_version
  verify/        pre-commit validators, one per action type (§8 step 5)
  approvals/     maker-checker bound to ActionDigest (ADR-011)
  idempotency/   UNIQUE(actor_scope, operation_type, key) + payload digest
  outbox/ receipts/   same-transaction outbox; per-run receipt hash chain
  ns/            namespace create / load / export / state-hash / delete (ADR-015)
  api/internal   gateway service JWT only · api/admin operator · api/review humans
  security/      one filter chain per realm
resources/db/migration/   V###__*.sql (.claude/rules/migrations.md)
```
## Commands
`make test-ledger` · `make test-int` · `./gradlew :services:ledger:bootRun`
## Conventions
- Write path = validate → approval/idempotency → ONE @Transactional commit (domain change + receipt + outbox) → typed result. Errors only from the contracts ErrorCode enum.
- Test names carry spec IDs: `T_SWE_02_concurrentDuplicatesHaveOneEffect`, `T_DOM_01_…`.
- Testcontainers singleton containers (one Postgres/Kafka per test JVM) — Om's laptop has 16 GB. Local runs -Xmx512m, Gradle workers ≤ 4.
- Read first: §5 §8 §9 §12 shards; ADR-015/016/017.
