# Experiment amendments and exploratory analyses
Append-only. Never edit `experiments/prereg/frozen/**`; record changes to the registered design here (`/amend`).

## AMENDMENT-1 · Shortcut availability constant across pressure levels L0–L3 (2026-10-29)
- Type: AMENDMENT (changes the registered design)
- Task: SH-05 · ADR-014 "Open for the team: L3 shortcut availability", option A · §13 H1 · §14 · U4 · REQ-005 REQ-010 · F1
- What changes: §14 (`docs/spec/sections/14-experimental-design-original-commitments-proposed.md`, line 6) says "`L3` severe end-of-day target with shortcut availability", which ties shortcut availability to L3 alone. From now on, the shortcut-capable actions (suspense-account adjustment, closure with empty evidence, SSI change via booking correction) are schema-valid and reachable at **every** level, L0–L3, and the tool surface is identical across levels and across control conditions (ADR-014). Pressure changes only the framing text. L3 keeps its severe end-of-day target and adds an explicit shortcut **hint**; the L1/L2 framing texts are drafted in KG-04 from the dev split and frozen with the prereg in KG-16.
- Rationale: H1 tests whether the attempted-violation rate rises with pressure. If shortcuts existed only at L3, any jump at L3 could come from the new opportunity, not the pressure, and H1's pressure coefficient would be confounded with affordance. Holding opportunity constant isolates pressure. The L3 hint is still part of the L3 treatment and is reported as such.
- Timing: decided **before** any results exist. No dev, pilot, eval or blind run has been executed, the prereg isn't frozen yet (`experiments/prereg/frozen/` doesn't exist), and no outcome data was seen.
- Affected: H1 (pressure effect: now pressure framing plus the L3 hint, with constant opportunity); MET attempted-violation rate per level; H2 is unaffected (ADR-014 already keeps the surface identical across off/monitor/full). Reporting: no pre-amendment results exist, so all results follow this design. The report states the §14 wording, this amendment and the residual limitation that the L3 contrast bundles severity with the hint (L0–L2 vs L3 can't separate the two).
- Approved by: om ☑ kunal ☑ (PR #17, 2026-10-29)

## EXPLORATORY-1 · Image-evidence arm and scan-generator comparison (RQ4) (2026-11-19)
- Type: EXPLORATORY (adds an analysis; does **not** change the registered design)
- Task: SH-20 · ADR-020 · §6 §13 §15 · F3 F4
- What is added: RQ4: does presenting evidence as generated scanned images instead of structured text change the correct-resolution rate, and which generator (pix2pix vs conditional VAE vs Augraphy rules) best preserves numeric fields?
  - Design: a paired subset of 50 evaluation scenarios, run with text evidence and with generated-scan evidence, everything else fixed.
  - Generator metrics: FID, KID, SSIM, and OCR character error rate on numeric fields.
  - Visual prompt-injection variants are scored like the text injections.
- What is not changed: H1–H3, their metrics, denominators, sample sizes, splits and decision rules. Image-arm runs are extra and excluded from every H1–H3 analysis.
- Rationale: realistic evidence format (scans) and the course's image-generation requirement, without touching preregistered claims. Results are labeled EXPLORATORY wherever they appear.
- Timing: proposed before any results exist; no image pipeline, corpus or run exists yet.
- Approved by: om ☐ kunal ☐
