## 12. OUTBOX, AUDIT, REPLAY, CONCURRENCY AND RELIABILITY

**Transaction outbox:** On each committed action, persist the financial change and an immutable outbox record in one DB transaction. Relay publishes with a stable `event_id` and `run_id`, retries on failure and may duplicate messages; Kafka is not the financial truth. Consumer deduplication/event idempotence required. Outbox backlog and consumer lag are observable SLOs. Preserve ordering within a keyed stream as needed; never assume global ordering across partitions/services.

**Event envelope:** `event_id`, `run_id`, `scenario_id`, `break_id`, `actor_id`, `action_id`, `event_type`, `schema_version`, `occurred_at`, `committed_at`, `aggregate_id`, `aggregate_version`, `correlation_id`, `causation_id`, `policy_decision_id`, `payload_hash`, `evidence_hashes`, `transaction_id`, `redaction_class`. Hashes and receipt identifiers should survive serialization/version upgrades. Sensitive fields never sent to anonymous telemetry.

**Tamper-evident receipts:** Chain each decision/action/denial with canonicalized record digest; periodic signature+off-system/public checkpoint as feasible; verification CLI checks hashes, signatures, missing/reordered records, associated policy and evidence versions. A simple hash chain without trusted external checkpoint is NOT strong tamper-resistance to privileged rewriting. Signature profile (algorithm/canonicalization/key rotation) documented in ADR. Denied actions must be preserved as first-class evidence.

**Counterfactual replay — two separate modes:**

1. **Action replay (deterministic control comparison):** Snapshot canonical initial ledger, record an immutable sequence of proposed tool actions from a previous run, reset isolated ledger, replay *the same proposed actions* through alternate gateway/policy versions, collect allow/deny/commit and financial state delta. This isolates control effect and does **not** show how an agent would adapt.
2. **Paired live agent execution:** Reset scenario to identical initial canonical state, run independently under different controls using same model/prompt/settings/scenario, record new generated action paths, grade each; multiple replications account for LLM nondeterminism. This captures adaptation and end-to-end effect but is not identical-action causality.

**Replay protections:** Immutable snapshot ID/hash, isolated scenario namespace, consistent timestamp/time-control and synthetic external message fixtures, stored version manifests, reset verification, no hidden truth to agent, no message duplication across runs, reproducible sampling settings, explicit outcome provenance.

**Chaos/failure matrix:** Restart service between financial DB commit and outbox publish; duplicate publishing; consumer outage/backlog; delayed/reordered messages; Redis outage; OPA unavailable; approval expiration; version race; model timeout; concurrent duplicate submissions; network partition; invalid tool schemas; partial UI disconnection; kill switch after a prior committed action. Define expected allowed/denied/recovery states for each. Toxiproxy or targeted injection is appropriate; record whether the platform safely fails closed for high-risk actions.

