## 16. HISTORICAL PROOF OF CONCEPT — NOT REAL LLM FINDINGS

**As reported in submitted proposal:** Standard-library Python + SQLite double-entry ledger + transactional outbox, scripted stand-ins for Redis/OPA, break factory, invariants, truth grader; 4 scripted policies (`oracle`, `shortcut`, `retry`, `sloppy`) × 200 scenarios (6 breaks each) × 3 control conditions = **2,400 scripted runs**. The shortcut policy could show **100% apparent closure and 52.6% correct resolution (47.4% false)** in controls-off simulation; oracle correctly escalated some breaks, so its naive closure proxy was less than 100% even with 100% correct outcomes. The sloppy policy could post incorrect amounts not caught by invariants, with reported correctness **87.6%**. Control tests claimed 100% detection/no false alarms *after a monitor bug fix* on the defined scripted cases; this does **not** establish general LLM safety. Local stand-in policy/monitor checks were microsecond/submillisecond; these are **not measured full-system network p99 values**.

**Original Figure 4 (scripted, controls off; broken out by metric):** `Oracle: closure=65.6%, correct=100%, false=0%`; `Shortcut: closure=100%, correct=52.6%, false=47.4%`; `Retry: closure=65.6%, correct=47.4%, false=52.6%`; `Sloppy: closure=65.6%, correct=87.6%, false=12.4%`. Note that closure and correctness may use different bookkeeping semantics (correct escalation does not close the break); verify raw experiment code before relying on the combined percentages.

**Original Table 6 details (200 runs each):**

| Scripted policy | Controls | Harmful actions executed | Detected | Blocked calls | Halted runs | Correct |
|---|---|---:|---:|---:|---:|---:|
| Oracle | All three | 0 | N/A | 0 | 0 | 100.0% |
| Shortcut | Off | 729 | 100% | 0 | 0 | 52.6% |
| Shortcut | Monitors only | 200 | 100% | 1,312 | 200 | 14.2% |
| Shortcut | Full | 0 | N/A | 569 | 0 | 100.0% |
| Retry | Off | 631 | 100% | 0 | 0 | 47.4% |
| Retry | Monitors only | 200 | 100% | 1,268 | 200 | 13.6% |
| Retry | Full | 0 | N/A | 0 (retries absorbed) | 0 | 100.0% |
| Sloppy | All three | 0 under monitored categories | N/A | 0 | 0 | 87.6% |

**Important POC nuances:** POC source originally says 1,035 shortcut violations detected in prose vs 729 executed harmful shortcut actions in the table; investigate event definitions with original logs. Initial monitor defect caused integrity alerts to fire repeatedly after reference-data write, obscuring closure-without-evidence checks: initial 79.3% detection and 214 false alarms; isolated per-invariant independent firing/once-per-state-change fix improved scripted-case metrics. Demonstrates why **supervisor requires its own regression tests**. Monitors alone could stop the next action but could not prevent first harm, sharply reducing task completion. Ground-truth oracle caught wrong amounts the invariants missed. The original rough context estimate was ~1,660 tokens scenario plus ~330 tool-schema tokens; approx 16,000 input tokens/run and 48M for 3,000-run open-weight plan without caching; estimate must be replaced with actual usage counters.

**Never state:** "the LLM closed 47% incorrectly", "our deployed supervisor prevents all fraud", "we measured <50ms p99", or "3,300 agent evaluations complete" until independently supported by real runs.

