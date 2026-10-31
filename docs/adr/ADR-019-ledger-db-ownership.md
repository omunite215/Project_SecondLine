# ADR-019: Ledger DB ownership: migrator owns the schema, the running ledger gets DML only
Status: PROPOSED (om ☐ kunal ☐, PR #)
Date: 2026-10-30 · Spec: §7 §9 §11 (SEC-02, SEC-12) · ADR-002, ADR-004, ADR-016 · REQ-002 · T-DOM-05 · Tasks affected: OM-03 (this change), OM-01 (infra/db/init), OM-07 (ledger trust boundary), OM-14 (receipts)

## Context
OM-01's `00-roles.sql` made `ledger_app` the owner of schema `ledger`, and the running ledger logs in as `ledger_svc`, which is a member of `ledger_app`. Had Flyway run as the app, the app would have owned every table. A bug, or a compromise of the ledger process, could then run `ALTER TABLE … DISABLE TRIGGER`, `DROP TRIGGER` or `DROP SCHEMA ledger CASCADE`. In that setup the immutability trigger that T-DOM-05 and SEC-12 rely on would only show that a trigger exists, not that history can't be rewritten.

## Options (≤3, with tradeoffs)
1. **The app owns the tables and immutability rests on the trigger.** No infra change, but the protected component can switch off its own protection.
2. **A separate migrator role owns the schema, and the app gets DML only** (chosen). One more login role and secret, plus a one-shot compose service. Immutability then holds even if the ledger process is compromised: the ledger has no UPDATE/DELETE grant on the ledgers, and the trigger is a second layer.
3. **Migrations run as the `postgres` superuser.** No new role, but the superuser password would have to sit in the ledger or migrate container, and the superuser bypasses every grant.

## Decision
- `ledger_migrator` (NOLOGIN group) owns schema `ledger` and every object in it. Its login `ledger_migrator_svc` (secret `LEDGER_MIGRATOR_PASSWORD`, created by `make bootstrap`) is used **only** by Flyway, through `SET ROLE ledger_migrator`.
- Flyway runs in the one-shot compose service `ledger-migrate`: the ledger image with profile `migrate`, no web server, exiting after the migration. The running `ledger` waits on `service_completed_successfully` and is never given the migrator password. `spring.flyway.enabled` is false by default.
- The OM-01 default that gave `ledger_app` full DML on tables created by `postgres` in `ledger` is removed. A superuser-created table there gives the app nothing.
- `ledger_app` gets:
  - `USAGE` on the schema;
  - `SELECT, INSERT` on all tables and `USAGE` on sequences, via default privileges;
  - `UPDATE` granted per table in migrations, only for mutable read models (`breaks.state_version`, `positions`);
  - never `DELETE`, never `CREATE`, never ownership.
- The immutability triggers stay as defence in depth, for example against a migrator mistake.

## Consequences (tests, tasks, risks)
- Tests (`OM_03_RolesTest`) run against the shipped `infra/db/init` scripts in Testcontainers:
  - the app can't `DROP SCHEMA`, `DISABLE TRIGGER` or `CREATE TABLE` (SQLState 42501);
  - the migrator owns the schema and all tables;
  - a re-run applies 0 migrations.
- Existing local volumes: `00-roles.sql` runs only on an empty data volume, so a developer with an old volume needs `make reset` once. Rerun `make bootstrap` first; it now appends missing keys to an existing `.env` and keeps its values.
- OM-07 builds on this: the ledger's DB identity can't escalate itself.
- Risk: a superuser (`postgres`) can still rewrite anything. That is ADR-018's A3/A4 attacker, which checkpoints address. This ADR doesn't claim otherwise.

## Verification (how we'll know it holds)
- SCRIPTED, in CI on every ledger change (`make test-ledger`, Testcontainers `postgres:17.11-alpine` initialised with the shipped `infra/db/init`):
  - `OM_03_RolesTest` covers the schema owner, no DROP/DISABLE TRIGGER/CREATE for the app, no forged Flyway history, and no UPDATE/DELETE even on a table `postgres` creates in `ledger`;
  - `OM_03_LedgerDbTest` covers the ledgers: append-only, closed once committed, reversal rules.
- VERIFY (local run, 2026-10-30, not yet in CI): on a fresh volume, `make up PROFILES="core app"` ends with `ledger-migrate` exiting 0 after applying V001–V004, `ledger` healthy, every `ledger` table owned by `ledger_migrator`, and no migrator secret in the `ledger` container's environment. To reproduce:
  - `docker compose -p <scratch> … up -d --wait postgres ledger-migrate ledger`;
  - then `SELECT tableowner FROM pg_tables WHERE schemaname='ledger'`;
  - then `docker compose -p <scratch> down -v`.
