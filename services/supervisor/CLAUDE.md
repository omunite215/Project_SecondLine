# services/supervisor — async detective monitors (owner: Kunal · rules reviewed by Om)
Python · Kafka consumer (pick confluent-kafka or aiokafka once and pin it). Consumes `ledger.events`; can halt FUTURE actions; never undoes commits (ADR-004).
```text
src/sl_supervisor/consumer.py   dedupe by event_id; ordering only within a key
src/sl_supervisor/state.py      per-run state
src/sl_supervisor/invariants/   I9 suspense growth · I10 cross-action transitions · I11 freshness/as-of · I12 audit-sequence gaps
src/sl_supervisor/halt.py       Redis halt flag + POST /internal/v1/runs/{id}:halt (service token)
src/sl_supervisor/incidents.py  incident records; metrics: consumer lag, detection delay
```
Commands: `make test-supervisor`
- Alert once per state change (the PoC's repeat-alert defect); every invariant has true-positive AND false-alarm tests.
- Thresholds tuned on dev only; frozen before KG-18.
