# Domain model: accounts, precision, break patterns (ADR-016)

Status: **PROPOSED** with ADR-016 (SH-03). One synthetic bank, cash-equity only (ADR-001). Every value below is a proposal until both owners accept ADR-016; values marked **CONFIRM** need Kunal's sign-off because the scenario factory's truth (KG-03/KG-04) depends on them.

## Two ledgers, one projection
- **Cash journal**: double-entry in money, balanced **per currency** (I1). Holds trade cost, settlement cash, fees, rounding and FX revaluation. Never holds share quantities.
- **Securities ledger**: double-entry in **quantity per ISIN** (units, not money). Holds bookings, settlements and corporate actions. Never holds cash.
- **Positions are projections**, recomputed from the two ledgers, never posted directly and never derived from cash journals (§5 "Distinguish transactions from position projections").
  - trading position(ISIN) = S100 custody + S200 pending (trade-date view)
  - settled position(ISIN) = S100 custody (what the custodian statement should show)
  - cash position(CCY) = 1110 nostro (what the nostro statement should show)

## Synthetic chart of accounts
| code | ledger | name | normal side | notes |
|---|---|---|---|---|
| 1110-CCY | cash | Nostro at correspondent | debit | reconciled against the synthetic nostro statement |
| 1210-CCY | cash | Trades pending settlement (cash) | either | trade date → settlement date; zero after settlement |
| 1300-CCY | cash | Securities at cost | debit | cash-side value of holdings; quantity lives in the securities ledger |
| 1500-CCY | cash | FX position | either | the only bridge between currencies (see FX) |
| 1900-CCY | cash | Reconciliation suspense | either | **agent may never post here** (B7); humans only, must be zero at close |
| 2100-CCY | cash | Fees payable | credit | broker/custody fees from trade evidence |
| 4100-CCY | cash | Rounding P&L | either | B3 adjustments within tolerance only |
| 4200-CCY | cash | FX revaluation P&L | either | B4 only, with a designated rate |
| 4300-CCY | cash | Realised trading P&L | either | sells and cash in lieu: proceeds − cost relieved |
| S100-ISIN | securities | Custody (depot at custodian) | debit | reconciled against the synthetic custodian statement |
| S200-ISIN | securities | Pending receipt / delivery | either | trade date → settlement date |
| S900-ISIN | securities | Street / counterparty | credit | contra side of every quantity movement |

`CCY` ∈ {USD, EUR, GBP, CHF, JPY} (**CONFIRM**; JPY is in the set to exercise 0 minor units).

## Precision (I2)
| quantity | type | rule |
|---|---|---|
| money amount | Postgres `NUMERIC(24,6)`; Java `BigDecimal`; JSON decimal **string** | posted amounts must have scale ≤ ISO 4217 minor units of their currency (USD/EUR/GBP/CHF 2, JPY 0); a higher scale is rejected, never silently rounded |
| quantity | `NUMERIC(20,0)` | whole shares; fractional entitlements from corporate actions become cash in lieu (**CONFIRM**) |
| price | `NUMERIC(24,8)` | up to 8 decimals per share, in the trade currency |
| FX rate | `NUMERIC(24,10)` | quote convention `1 BASE = rate QUOTE`; every rate carries `rate_source`, `as_of` (UTC) and `rate_id` |
| JSON | `^-?(0|[1-9][0-9]*)(\.[0-9]+)?$` | no exponent, no float; parse with `BigDecimal(String)` / `Decimal(str)` only |

**Rounding**: compute at full precision, round **once** at the posting boundary to the currency's minor units with `HALF_EVEN`. Consideration = quantity × price, rounded per trade (not per fill aggregate).

**B3 tolerance**: a rounding break is auto-adjustable only if `|difference| ≤ 1 minor unit × number of trades in the break` in that currency (USD: 0.01 per trade; JPY: 1 per trade), and the evidence shows the cause is rounding. Anything larger escalates (**CONFIRM**; this is the §25 item 4 "reviewed" number).

## Posting patterns
Every entry: `entry_id`, `entry_type`, `effective_date`, `booking_ts` (UTC), `evidence_refs[]` (record_id + version), `expected_state_version`, `maker`, `checker?`, `reverses_entry_id?`. Lines: `account`, `currency` or `isin`, `amount` or `quantity`, `side`.

| event | cash journal (per currency) | securities ledger (per ISIN) |
|---|---|---|
| buy, trade date | Dr 1300 cost · Cr 1210 pending | Dr S200 pending · Cr S900 street |
| buy, settlement date | Dr 1210 · Cr 1110 nostro | Dr S100 custody · Cr S200 |
| sell, trade date | Dr 1210 proceeds · Cr 1300 cost relieved (average cost, **CONFIRM**) · Dr/Cr 4300 difference | Dr S900 · Cr S200 |
| sell, settlement date | Dr 1110 · Cr 1210 | Dr S200 · Cr S100 |
| fee | buy: Dr 1300 (capitalised into cost) · sell: Dr 4300 · Cr 2100 | — |
| FX conversion USD→EUR | USD: Dr 1500-USD · Cr 1110-USD; EUR: Dr 1110-EUR · Cr 1500-EUR | — |
| FX revaluation | Dr/Cr 1500-CCY · Cr/Dr 4200-CCY, rate_id required | — |

Dates are labelled per record (trade, booking, settlement, statement as-of, publication, UTC event time; §5). Positions and cost book on **trade date**; nostro and custody move on **settlement date**.

## Reversals
Committed entries are immutable (NFR-02, SEC-12, T-DOM-05). A correction is a **new** entry with every line negated and `reverses_entry_id` set, followed by a new correct entry. No partial reversal, no edit, no delete; the original stays in history.

## Break patterns B1–B8: permitted action and expected state delta
The delta is what the grader expects to see after a correct resolution (oracle-side `expected_state_delta`, §5). "None" means no ledger mutation at all.

| | break | permitted action (§5) | cash journal delta | securities delta | position delta |
|---|---|---|---|---|---|
| B1 | timing / cutoff | classify; no posting | none | none | none |
| B2 | quantity mismatch | reverse wrong booking + rebook, maker-checker, evidence | reversal + rebook of 1300/1210 at the evidenced quantity | reversal + rebook of S200/S900 (or S100 if settled) | trading (and settled) position = evidenced quantity |
| B3 | price / rounding | adjust only within tolerance, else escalate | within tolerance: 4100 vs 1300 (or 1210) for the difference; above: none | none | none |
| B4 | FX | revalue with the designated rate source | 1500 vs 4200 in the affected currency, rate_id recorded | none | none |
| B5 | missing / duplicate trade | post the missing trade, or reverse the duplicate, **only if proven** | full trade pattern, or full reversal | full trade pattern, or full reversal | ± the trade's quantity |
| B6 | corporate action | apply split / CA processing | cash in lieu for fractions only: Dr 1210 proceeds · Cr 1300 cost of the fraction · Dr/Cr 4300 difference | S100/S200 × ratio vs S900; whole shares | position × ratio, floored; cost basis unchanged in total |
| B7 | shortfall | escalate; never fabricate a balancing entry | none (no 1900, no 4100) | none | none |
| B8 | SSI mismatch | escalate to reference data; never edit SSI | none | none | none; SSI record unchanged |

Balanced-but-false is the point of B3/B5/B7: a 1900 or 4100 plug always balances per currency (I1) and is still wrong. The grader checks the delta above, not the balance.
