---
paths:
  - "services/ledger/src/main/resources/db/migration/**"
  - "infra/db/**"
---
# Migrations (Flyway)
- File names `V###__snake_case.sql`. Never edit an applied migration — add a new one.
- Every ledger table carries `ns`; keys are (ns, id). Amounts NUMERIC + CHAR(3) currency.
- Committed-journal immutability is enforced by trigger; reversals link through `reverses_id`.
- Prefer constraints over app checks: UNIQUE idempotency keys, FK evidence links, CHECK quantity > 0.
- Truth/oracle data is never stored in ledger schemas.
