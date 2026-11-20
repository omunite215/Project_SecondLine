# packages/scenario-factory — causal world + hidden truth (owner: Kunal) — PRIVILEGED
Python. Build the CAUSE first, then the observable records (§5). Outputs per contracts: WorldBundle (visible) + Truth (privileged) + manifest.
```text
src/sl_factory/rng.py world.py        seeded sub-streams, opaque ids, canary; QZ ISINs, markets/cutoffs, currencies
src/sl_factory/lifecycle.py            causal events + TradeSim facts (true vs booked) — the CAUSE
src/sl_factory/breaks/                 b1_timing.py b2_quantity.py b3_price_rounding.py (KG-03) … b8 (KG-04) → BreakPlan
src/sl_factory/render.py               facts → WorldBundle, then reconcile() finds breaks from visible records only
src/sl_factory/generate.py __main__.py one scenario; `python -m sl_factory generate --split dev --n 40`
src/sl_factory/categories.py           the 11 §5 scenario categories
src/sl_factory/splits.py               dev / eval / blind templates + fingerprints
src/sl_factory/attacks.py              applies OM-16 attack packs from data/attacks/
src/sl_factory/canonical.py version.py  sorted compact JSON + sha256; GENERATOR_VERSION (bump if bytes change)
```
Commands: `make factory SPLIT=dev N=40 [OUT=dir]` · `make factory-all` (KG-04) · `make test-factory` · `make leakage-check` (KG-05)
Output: data/generated/<split>/{bundles,manifests}/ (visible) · truth/ + truth/explanations/ (privileged) · MANIFEST.json (hashes)
- Visible records show SYMPTOMS, never root causes; ids are opaque.
- Same seed ⇒ same bytes ⇒ same sha256 (no wall clock, no unordered iteration).
- Eval/blind outputs go only to data/generated/{eval,blind}/ (Claude can't read them) — debug on dev.
- Money as Decimal; FX only from data/reference snapshots, cited by snapshot id.
