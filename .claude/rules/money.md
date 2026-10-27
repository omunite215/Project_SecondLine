---
paths:
  - "services/ledger/**"
  - "services/gateway/**"
  - "libs/contracts-java/**"
  - "packages/contracts/**"
  - "packages/scenario-factory/**"
  - "packages/evaluation/**"
---
# Money, quantities, prices, time
- Java: BigDecimal with the scale ADR-016 defines; RoundingMode only where the ADR names one; compare with `compareTo`, never `equals`.
- Python: `decimal.Decimal`; JSON carries money as strings, never floats.
- Postgres: NUMERIC(p,s) per ADR-016, with a CHAR(3) ISO 4217 currency next to every amount; minor units come from a table, not literals.
- Journals: Σ debit = Σ credit per currency inside the DB transaction. FX conversion only through the designated rate source + snapshot id.
- Corrections append reversing/compensating entries; committed rows are immutable.
- Quantity/position changes are their own domain transactions — never invented cash journal entries.
- Store UTC instants AND explicit business dates (trade, settlement, statement as-of); never derive one from the other implicitly.
