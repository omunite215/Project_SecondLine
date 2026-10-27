## 11. POLICY, IDENTITY AND SECURITY THREAT MODEL

**Threat boundaries:** User and agent identities; MCP request channel; text from custodian/counterparty (untrusted); run/gateway service; OPA policy; ledger/database; audit/export; oracle grader; human reviewer. **Trust hierarchy:** financial truth / policy and identity are server controlled; model-generated text and external documents are untrusted. UI is never a security boundary. Tools are capabilities, not unguarded network endpoints.

**Identity scheme (course-suitable):** short-lived signed service tokens with audience, subject, allowed operation, run ID, scenario/tenant scope, expiry, approval constraints; server verifies token on every sensitive call. Service-to-service authenticated channel. OAuth/OpenID/MCP authorization when interoperable remote MCP is used; follow *pinned* applicable MCP specification revision. Do not prematurely implement full enterprise IAM. UI reviewer and maker identities separate, even if local synthetic accounts.

**Policy decisions:** `ALLOW`, `DENY`, `REQUIRE_APPROVAL`; every decision includes policy bundle version/hash and deterministic reason; tests cover default-deny, roles, break types, posting limits, permitted accounts, suspense restrictions, reference-data immutability, approval thresholds and toxic sequences as applicable. No model is allowed to instruct OPA to change its own rules. Redis kill switch is advisory fast path; durable run status must also be enforced when consequential writes commit.

| Threat ID | Attack / failure | Defensive evidence and test |
|---|---|---|
| SEC-01 | Indirect prompt injection in memo/email/status text | Tool data treated as content, never elevated into system/tool policy; injection cases graded |
| SEC-02 | Agent bypasses gateway via direct ledger API | Ledger verifies service identity and authorization; direct-agent credential denied (`T-SEC-01`) |
| SEC-03 | Permission overreach / policy bypass | OPA default-deny, scoped signed token, downstream recheck (`T-SEC-02`) |
| SEC-04 | Authorized sequence creates fraudulent result | Cross-action state monitor + pre-commit invariants + oracle, sequence attacks (`T-SEC-03`) |
| SEC-05 | Balanced but economically incorrect posting | Record-level evidence validation and independent adjudication (`T-DOM-04`) |
| SEC-06 | Stale evidence or reviewer approval / TOCTOU | Canonical payload+version hash, expires/re-approves on change (`T-SEC-04`) |
| SEC-07 | Double posting from retry / race | DB unique key, payload binding, transaction, concurrent integration test (`T-SWE-02`) |
| SEC-08 | Lost Kafka consumer/delayed outbox | Commit+outbox atomic; eventual at-least-once; lag monitor/replay (`T-SWE-03`) |
| SEC-09 | Audit log rewritten by privileged service | Hash chain, signed digest and independently retained checkpoint, offline verifier (`T-SEC-05`) |
| SEC-10 | Reviewer rubber stamps approvals | Show evidence/action delta, require reason code, separate maker/checker, log all decisions |
| SEC-11 | Leakage of hidden labels/API keys | Access separation, sanitized traces, secret scanning (`T-SEC-06`) |
| SEC-12 | Error recovery silently mutates prior journal | Append reversal/compensating action only; record attribution (`T-DOM-05`) |
| SEC-13 | Unbounded agent action/cost | Run budget, tool budget, timeout, emergency halt (`T-SEC-07`) |
| SEC-14 | Wrong / adversarial data-source identity | Fixture signatures/hashes, provenance, external content isolation |

**Fail-safe defaults:** When unable to verify authorization, evidence, state version or approval, **do not mutate**. If optional async Kafka consumer is unavailable, allow only those actions whose synchronous safety checks remain valid; record monitor-degraded state, impose risk-based restriction/deny for operations requiring active supervision. Recover using outbox and replay. No concealment of partial failure.

