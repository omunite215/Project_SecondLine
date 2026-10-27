# packages/audit-verifier — independent receipt-chain verifier (owner: Kunal)
Python, deliberately independent of the Java implementation (same spec, different code). Must pass packages/contracts/test-vectors/receipts.
CLI: `sl-verify <run-export.json> [--anchors experiments/anchors/]` → hashes, chain links, signatures, gaps/reorders, missing denials.
Document what it cannot detect (e.g. privileged rewrite without an external anchor) per ADR-018.
Commands: `make verify-chain RUN=<id>` · `make test-py`
