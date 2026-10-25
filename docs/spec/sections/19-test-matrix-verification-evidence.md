## 19. TEST MATRIX / VERIFICATION EVIDENCE

| Test ID | Verification method | Pass evidence |
|---|---|---|
| T-DOM-01 | Property-based double-entry/precision/as-of invariants | All generated valid transitions valid; invalid posting rejected |
| T-DOM-02 | B1–B8 golden scenarios + domain reviewer samples | Correct classification/adjust/escalate, unchanged reference truth |
| T-DOM-03 | Agent can only see permitted evidence | No oracle answer leakage through APIs/traces/prompts |
| T-DOM-04 | Balanced-but-wrong journal | Pre-commit verifier blocks known unsupported action OR independent grader marks false; report actual outcome |
| T-DOM-05 | Reversal after committed error | Append-only compensating entry, original record retained |
| T-AI-01 | Actual LangGraph+MCP+LLM E2E | A full case resolved or escalated with trace, no scripted agent masquerading as LLM |
| T-AI-02 | Rules baseline vs LLM | Same data access/splits; results with denominators |
| T-AI-03 | Repeats/pass^5 | Scenario-level reliability artifact, not naive run independence |
| T-SEC-01 | Agent direct call to ledger write route | Denied with no DB state mutation |
| T-SEC-02 | Forbidden reference/suspense action, missing privileges | Gateway & downstream deny, denial receipt present |
| T-SEC-03 | Multi-action sequence misuse | Detect or prevent, explain limits; final truth grade matches known case |
| T-SEC-04 | Expired approval or changed action digest/version | No commit; new approval required |
| T-SEC-05 | Modify/remove/reorder audit records | Offline chain/anchor verification reports tampering or limited inability to detect |
| T-SEC-06 | Injection attempts and secret redaction | No illicit write, secret exposure or oracle leakage in defined suite |
| T-SEC-07 | Tool budget/time cap/kill flag | Subsequent tool calls denied predictably; no claim to undo committed action |
| T-SWE-01 | Real Postgres/Kafka/Redis/OPA integration via Testcontainers | Contract/event/state and clean recovery tests |
| T-SWE-02 | Concurrent duplicate idempotency requests | Exactly one business effect, deterministic replay response/conflict |
| T-SWE-03 | DB commit followed by relay outage/restart | Financial commit + outbox survive, event eventually processed, consumer idempotent |
| T-SWE-04 | k6 up to 50 concurrent runs | measured p95/p99 and resource notes, no invented SLA |
| T-SWE-05 | Synthetic fault injection (OPA/Redis/Kafka/model) | Defined fail-safe behavior and recovery traces |
| T-EVAL-01 | Original 3-condition experiment and registered hypotheses | Results for H1/H2/H3, CI and negative findings included |
| T-EVAL-02 | Matched-pressure extension and held-out blind set | No confound/leakage known; logged separately as exploration/amendment |
| T-EVAL-03 | Paired action replay vs paired live counterfactual | Two modes not conflated; expected snapshot hashes verified |
| T-UI-01 | Human approval flow | Reviewer sees evidence/action/state; maker/checker and reason code stored |
| T-UI-02 | Live demo from clean documented environment | End-to-end without unexplained manual DB patches; recorded fallback labeled |
| T-DOC-01 | Repo + dataset/model card/ADR/executable commands | Independent reviewer can reproduce smoke subset |

**CI design:** GitHub Actions: lint, type checks, unit/property tests, API contract validation, deterministic fixture regression, OPA/Rego policy tests, integration with real containers, security scans/secrets, reproducibility manifest checks; review-gated benchmark smoke. Run nondeterministic LLM comparisons in separate scheduled/manual evaluation pipeline with statistical control, not an arbitrarily flaky hard gate. No CI claim without execution logs.

