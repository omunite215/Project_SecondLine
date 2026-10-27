## 6. DATASETS, PROVENANCE AND QUALITY

- **GLEIF LEI datasets/mappings:** Public entity-ID grounding; snapshot with retrieval time, license, hash, missing-coverage rate; no claim that LEI alone identifies a settlement account. Proposed CC0 source in submission.
- **ECB EUR reference FX:** Information-only reference rates, not executable transaction prices. Snapshot and explicitly document fixing/publication time, date, currency availability, provenance/license.
- **U.S. Federal Reserve H.10 FX:** Alternative public rate with differing methodology/timing. Only compare aligned eligible calendar dates and well-defined currency pairs. Never treat both as exchangeable execution rates.
- **ISO 20022 / ECB T2S statuses:** Use carefully verified official codes for synthetic settlement reports; retain meaning/citations and caveats.
- **AgentDojo / InjecAgent:** Ideas and permitted benchmark attack material; record original source, license, adaptation and leakage checks; held-out benchmark evaluation distinct from training/tuning.
- **JPMorgan Chase synthetic data program:** Optional, **access not guaranteed**; never a blocker. Use homegrown generator if unavailable.
- **Causal break factory:** Seeded, versioned, configurable; produce scenario manifest, datasheet and per-scenario hash; split generator templates/parameters between dev and held-out evaluation. Preserve hidden truth and detect accidental answer leakage.
- **Classmate/practitioner blind review:** Independently authored small set without access to monitor logic; domain reviewer ideally examines 20–30 challenging financial cases, or record explicit lack of review.

**Dataset documentation:** composition, motivation, generation algorithm, splits, source snapshots/hashes, rights/licensing, exclusion criteria, label adjudication, synthetic-only scope, known fidelity limitations, intended/misuse cases. Keep dev/test isolation. Secrets only from environment/secret store; redact tokens and any accidental sensitive content from traces.

