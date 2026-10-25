# packages/scenario-factory — causal world + hidden truth (owner: Kunal) — PRIVILEGED
Python. Build the CAUSE first, then the observable records (§5). Outputs per contracts: WorldBundle (visible) + Truth (privileged) + manifest.
```text
src/sl_factory/world.py lifecycle.py   seeded institution, counterparties, instruments; causal event simulator
src/sl_factory/breaks/                 b1_timing.py … b8_ssi.py + hard variants
src/sl_factory/categories.py           the 11 §5 scenario categories
src/sl_factory/splits.py               dev / eval / blind templates + fingerprints
src/sl_factory/attacks.py              applies OM-16 attack packs from data/attacks/
src/sl_factory/bundle.py truth.py manifest.py canary.py
```
Commands: `make factory SPLIT=dev N=40` · `make factory-all` · `make test-factory` · `make leakage-check`
- Visible records show SYMPTOMS, never root causes; ids are opaque.
- Same seed ⇒ same bytes ⇒ same sha256 (no wall clock, no unordered iteration).
- Eval/blind outputs go only to data/generated/{eval,blind}/ (Claude can't read them) — debug on dev.
- Money as Decimal; FX only from data/reference snapshots, cited by snapshot id.
