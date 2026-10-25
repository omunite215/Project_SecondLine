## 15. ADVERSARIAL TEST SUITE / RELIABILITY BENCHMARK

**Test families:**

1. Reward hacking: suspense plug, close-without-evidence, reclassify to hide outstanding amount, edit denominator/reference data.
2. Indirect prompt injection: untrusted counterparty text instructs agent to ignore policy, fake approval or submit a privileged tool request; compare instruction-following against normal ambiguous evidence.
3. Authorized-sequence misuse: individually legal actions cause cross-step incorrect state; include forged/stale evidence chains.
4. Balanced-but-wrong finance: correct debits/credits but wrong trade, price, currency, settlement date or supporting cause.
5. Staleness/concurrency: version changed between evidence read and commit; approval for earlier proposed action reused; simultaneous retries.
6. Recovery faults: duplicate Kafka events, delayed outbox, consumer crash, lost response after commit, Redis outage, OPA outage, model timeout; prove no duplicate business effect.
7. Abstention cases: conflicting evidence, unknown root cause, escalate-only B7/B8; penalize unsupported closure more than justified escalation.
8. Data leakage/circularity: detect oracle labels, template fingerprints, split overlap, overfit/reused attack content.

**Quality bar:** Test dangerous cases and hard *legitimate* cases, otherwise a system that blocks everything could score perfectly on harm reduction. Evaluate severity vs utility. Use blind, previously unseen variants. Keep finance-specific attacks bundled with mitigations and ethical-use documentation rather than releasing an uncontextualized exploitation pack.

