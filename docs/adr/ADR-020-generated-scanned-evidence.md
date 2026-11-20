# ADR-020: Generated scanned-evidence images (image track, exploratory)
Status: PROPOSED
Date: 2026-11-19 · Resolves: course requirement for an image-generation component (AAI 6665 Final Assessment Proposal) · spec §6 §10 §13 §15 · Tasks affected: SH-20 (new), KG-03/KG-04 (renderer hook), KG-05 (leakage check), OM-06 (evidence tool returns an image), OM-16 (visual injection pack), KG-15/KG-18 (image arm)

## Context
- Real reconciliation evidence (custodian statements, trade confirmations, settlement notices) often arrives as PDFs, faxes and scans. Today every evidence record reaches the agent as structured text, so we never test whether the agent misreads a digit, which is exactly how a wrong-but-balanced posting starts (F3).
- The course's Final Assessment Proposal asks for an image-generation system with a justified GAN / VAE / hybrid choice. The scenario factory stays a structured causal generator (balance by construction, known root causes). The image component has to add value without weakening the hidden-truth answer key.
- Constraints:
  - **Truth isolation:** hidden truth, `truth_ref` and `SLCANARY-` canaries must not reach the agent, including through pixels (golden rule 4).
  - **Synthetic-only data:** no real records or PII (golden rule 2). Public scanned-document corpora such as RVL-CDIP come from real litigation documents, so they are out.
  - **Training hardware:** SH-19 says "no model training — Explorer only serves inference", so training must fit Om's RTX 3050 (4 GB) or Kunal's Mac.
  - **Preregistration:** H1–H3 are preregistered and must not change (golden rule 6).

## Options (≤3, with tradeoffs)
1. **Conditional GAN, pix2pix (paired), as primary; conditional VAE as learned comparison; Augraphy rules as non-learned baseline.**
   - Pros: L1 term ties output pixels to the input, which protects digits; a PatchGAN discriminator learns local scan texture; small 256 px tiles fit 4 GB; and we can make exact pairs by printing our own synthetic pages and scanning them.
   - Cons: needs page-to-scan alignment. CycleGAN is the fallback if alignment fails.
2. **Diffusion model:** probably the most realistic texture, but training it is out of reach on 4 GB and on our schedule. It can also invent detail (characters).
3. **Rule-based degradation only (Augraphy, MIT):** cheap and faithful, but nothing is learned. It doesn't meet the course requirement and gives no GAN-vs-VAE evidence.

## Decision
Option 1. The **scan generator, its OCR gate and the generator evaluation (pix2pix vs conditional VAE vs Augraphy) are a committed course deliverable** (the AAI 6665 proposal promises a working image generation system by Module 15). Only the **agent image arm** (RQ4) is exploratory, and it never changes H1–H3:
1. **Render (factory side, deterministic):** an evidence record becomes a clean page image (template, 200 dpi) with a visible `SYNTHETIC` watermark. It uses only the fictional bank's names and identifiers, with no real logos, letterheads or signatures.
2. **Degrade:** the scan generator (pix2pix; conditional VAE and Augraphy for comparison) works on 256×256 tiles.
3. **Verify (fail closed):** OCR reads every numeric field back (quantity, price, amount, date, identifier).
   - Any mismatch rejects the page, and the Augraphy baseline page is served instead.
   - Pages are also OCR-scanned for `SLCANARY-` strings, and any hit is a leakage failure.
4. **Serve:** for scenarios in the image arm only, the evidence tool returns the image instead of the text. The ledger, gateway authorization and grading are unchanged. The grader still reads factory truth, never pixels.
5. **Training data:** about 300 of our own synthetic pages, printed on two printers and scanned on two flatbeds and one phone app.
   - Splits are by template, so test layouts are unseen.
   - The corpus lives under `data/generated/` (gitignored) with a manifest and hashes.
6. **Release policy:** generator weights are not published, because a model that makes documents look scanned could help disguise forged paperwork.

## Consequences (tests, tasks, risks)
- **Contracts:** the evidence read path needs an image variant (a content type plus an image reference, not inline truth). That is a `packages/contracts/` bump → `make codegen` → `/handoff` → both approve. It's not done in this ADR.
- **Leakage (KG-05):** must OCR-scan generated pages for canaries and fail the build on a hit. `leakage-auditor` runs after the renderer and tool changes.
- **Experiment:** the image arm is EXPLORATORY-1 in `docs/experiment-amendments.md`.
  - It uses a paired subset of 50 evaluation scenarios (text vs image evidence, everything else fixed).
  - Generator metrics: FID, KID, SSIM, and OCR character error rate on numeric fields.
  - Visual prompt-injection variants join OM-16.
- **Cut order:** the generator, OCR gate and generator evaluation are protected, as a course deliverable. Only the agent image-arm runs can be cut (PLAN §7, after the console extras and load scale).
- **Risks:**
  - The generator alters a digit → the OCR gate catches it.
  - Alignment fails → CycleGAN.
  - Laptop VRAM is too small → smaller tiles or batch size; still no Explorer training without changing SH-19.
  - The OCR engine itself misreads clean pages → measure the OCR error on clean renders first and report it as the floor.

## Verification (how we'll know it holds)
- **OCR gate:** on the held-out template split, the chosen generator passes the gate (every numeric field exact) on ≥ 95% of pages.
- **Feasibility check (2026-11-19, EXPLORATORY):** 30 rendered pages, 1,200 fields per condition, RapidOCR.
  - Clean renders read 100%.
  - Augraphy heavy: 93.3% of fields but only 16.7% of pages fully exact.
  - Blur radius 3 px: 92.3% of fields, 0% of pages.
  - Per-page targets are therefore required, and blur (the VAE risk) is the main threat. No page that fails the check is ever served (test: inject a page with one digit changed and expect the baseline page).
- **Canaries:** a renderer test plants a canary in a non-evidence field and expects KG-05 to fail.
- **No training on Explorer:** `infra/hpc/` has no training job, and SH-19's rule stands unless amended.
- **Reported metrics:** FID, KID and SSIM against held-out real scans, plus OCR CER, for pix2pix vs conditional VAE vs Augraphy, labeled EXPLORATORY.
