# ADR-016: Accounting model & precision
Status: PROPOSED (om ☐ kunal ☐, PR #)
Date: 2026-10-29 · Resolves: U1 (§25 item 1) / §5 §8 §9 · Tasks affected: OM-03, OM-08, OM-02, SH-02, KG-03, KG-04, KG-06

## Context
U1 asks for the "precise accounting model: cash versus securities double-entry and position projection; selected account chart, price precision and permitted adjustment categories". The spec fixes the rules but no numbers:
- money is currency-aware decimal, never binary float (§5, NFR-02);
- journals balance **per currency**, with defined FX conversion accounting (§5, I1); precision and account policy are invariants (I2, §8);
- history is immutable, and corrections are compensating entries (§5, SEC-12, T-DOM-05);
- a balanced entry is necessary, not sufficient (§5);
- quantity/position corrections are their own domain transactions, never invented cash entries, and positions are projections (§5);
- the B1–B8 permitted actions (§5 table);
- thresholds are never unreviewed magic numbers (§25 item 4).

Unspecified: the chart of accounts, minor units, quantity/price/FX scale, rounding rule, the B3 tolerance, the trade-date vs settlement-date rule, and per-pattern state deltas. KG-03/KG-04 (truth) and OM-03/OM-08 (ledger, validators) both need these to be the same numbers.

## Options (≤3, with tradeoffs)
1. **Single cash journal; securities as valued cash accounts.** Simplest schema. But quantities ride on money amounts, so a quantity break (B2) or a split (B6) has to be expressed as a cash entry, which is exactly what §5 forbids. It also makes balanced-but-false plugs indistinguishable from real fixes.
2. **Two double-entry ledgers (cash per currency + securities per ISIN), with positions projected from both.** Matches §5's split and reconciles naturally against the two external statements (nostro → 1110, custodian → S100). Costs a second ledger and a projection, which OM-03 has to build and property-test.
3. **Event-sourced trades only; derive both ledgers on read.** Elegant replay, but the ledger is then a derivation rather than the authority (ADR-002), and the pre-commit verifier (ADR-004) has no committed balance to check. Too much machinery for the scope (RSK-12).

## Decision
Option 2, with the concrete tables in **docs/domain.md**:
- **Chart of accounts:**
  - cash: 1110 nostro, 1210 pending settlement, 1300 securities at cost, 1500 FX position, 1900 suspense (agent may never post), 2100 fees payable, 4100 rounding P&L, 4200 FX revaluation, 4300 realised P&L;
  - securities: S100 custody, S200 pending, S900 street.
- **Precision:**
  - money `NUMERIC(24,6)`, and a posted amount's scale must be ≤ the ISO 4217 minor units of its currency; a higher scale is rejected, never rounded silently;
  - quantity whole shares `NUMERIC(20,0)`, price `NUMERIC(24,8)`, FX rate `NUMERIC(24,10)` with source, as-of and id;
  - JSON values are decimal strings.
- **Rounding:** `HALF_EVEN`, once, at the posting boundary, per trade.
- **B3 tolerance:** ≤ 1 minor unit × trades in the break, with evidence that the cause is rounding; otherwise escalate.
- **Dates:** cost and trading position on trade date; nostro and custody on settlement date.
- **FX:** the only cross-currency bridge is 1500-CCY pairs, so every entry still balances per currency.
- **Reversals:** a full negating entry with `reverses_entry_id`, then a rebook. Never an edit, delete or partial reversal.
- **B1–B8:** permitted action and expected cash / securities / position delta per pattern, as in the docs/domain.md table. B7 and B8 have no mutation at all.

To confirm before ACCEPTED (Kunal, because the factory's truth uses them):
- (a) the currency set {USD, EUR, GBP, CHF, JPY};
- (b) the B3 tolerance;
- (c) cash in lieu for fractional CA entitlements;
- (d) average-cost relief on sells.

## Consequences (tests, tasks, risks)
- **OM-03** builds both ledgers and the projection. Property tests (jqwik):
  - per-currency balance for any generated entry;
  - projection(ledgers) equals the incrementally maintained positions;
  - a reversal plus rebook leaves history containing the original.
- **OM-08** validators reject:
  - scale above minor units;
  - an agent posting to 1900;
  - 4100 above tolerance;
  - quantity changes carried by cash-only entries;
  - an edit or delete of a committed entry.
- **SH-02**: the action and journal schemas use decimal strings and carry `evidence_refs` and `expected_state_version`; the account codes become an enum.
- **KG-03/KG-04**: `expected_state_delta` follows the B1–B8 table. B3/B5/B7 balanced-but-false cases use 1900/4100 plugs that balance and still fail grading.
- **Risk:** the numbers are synthetic proposals, not a bank's policy. The report must call them "synthetic accounting policy" (claims rule: mapping ≠ compliance). A domain reviewer (SH-11) should look before the report cites them.

## Verification (how we'll know it holds)
- Every B1–B8 golden scenario (T-DOM-02) resolves to exactly the delta in docs/domain.md, as graded by KG-06.
- OM-03 property tests: I1 per currency and I2 precision hold for 10k generated entries; a single float-typed amount anywhere fails CI (static check).
- A plug to 1900 or 4100 above tolerance is rejected pre-commit (OM-08) **and** graded wrong if forced through in `controls=off` (KG-06).
