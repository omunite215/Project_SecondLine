# services/supervisor — async detective monitors (owner: Kunal · rules reviewed by Om)
Python · Kafka consumer (pick confluent-kafka or aiokafka once and pin it). Consumes `ledger.events`; can halt FUTURE actions; never undoes commits (ADR-004).
```text
src/sl_supervisor/events.py     envelope → Event; monitored event types (KG-11 S2); JSONL source (Kafka with OM-13)
src/sl_supervisor/state.py      per-run / per-break state
src/sl_supervisor/invariants/   I9 suspense growth · I10 cross-action transitions · I11 freshness/as-of · I12 audit-sequence gaps
src/sl_supervisor/ledger.py     LedgerReader port: transaction lines by id (endpoint pending at Om, KG-11 S1)
src/sl_supervisor/supervisor.py dedupe, once-per-state-change alerts, HaltSink (Redis + OM-12 :halt), incidents, metrics
```
Commands: `make test-supervisor`
- Alert once per state change (the PoC's repeat-alert defect); every invariant has true-positive AND false-alarm tests.
- Thresholds tuned on dev only; frozen before KG-18.
