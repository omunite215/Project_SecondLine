## 18. QUALITY ATTRIBUTES / ACCEPTANCE TARGETS

| ID | Attribute | Bounded target / verification |
|---|---|---|
| NFR-01 | Domain safety | No unauthorized ledger mutation in defined negative tests; 0 duplicate business effects under retry/concurrency test matrix |
| NFR-02 | Financial correctness | Oracle verified state transitions, complete state resets, no floating-point money, immutable financial events |
| NFR-03 | Resilience | Outbox recovery after crash, replayable Kafka consumers, bounded queuing and correct degraded state under dependency failure |
| NFR-04 | Security | Direct-gateway bypass test denied; role/action/evidence scope, secrets excluded from logs |
| NFR-05 | Auditability | Every allowed/denied action has linked decision receipt and demonstrable chain verifier; identify unavailable proofs honestly |
| NFR-06 | Reproducibility | Every test run resolves to scenario snapshot/generator hash, model ID, inference settings, prompt/tool/policy code hashes, seed |
| NFR-07 | Experiment integrity | Original hypotheses reported without post-hoc outcome tuning; dev/eval/blind partitions enforced |
| NFR-08 | Performance | **H2 original target** incremental p99 ≤50 ms per tool call, separately report path and environment; measure under load |
| NFR-09 | Load | Original plan k6 with **50 concurrent runs**, if resources permit; do not imply fulfilled until tested |
| NFR-10 | Observability | OpenTelemetry trace across agent→gateway→ledger→outbox→supervisor, metrics for Kafka lag and audit failures |
| NFR-11 | Developer experience | Documented setup from clean machine, migrations, seeds, smoke tests; core local demo available independently of campus HPC |
| NFR-12 | Accessibility/product clarity | Clear labels, keyboard navigation, error states, role-aware financial action previews, honest status classification |

**No fake service-level promises:** These are proposed acceptance targets for **bounded synthetic test settings**. Platform uptime/real bank throughput and absolute inference p99 cannot be credibly guaranteed by a student deployment.

