# Source reconciliation & citation verification (SH-13)
Spec: §2 §16 §24 §6 · U13 · RSK-15 · B7 B8 · driver Kunal, reviewed by Om. Checked 2026-11-20.

Every claim in this file is marked **RESOLVED** (confirmed against the named source), **CORRECTED** (the claim or citation was wrong and the fix is given), or **UNRESOLVED** (it can't be confirmed with what we have, and the report carries it with its label and caveat). "Verified" here means existence and metadata. It is not a review of each source's content, except where a claim is quoted below.

## 1. PoC count discrepancy: 1,035 vs 729 (§2, §16, U13)
**UNRESOLVED.** Report both numbers as `POC-REPORTED` and never treat them as the same thing.

| claim | where it appears in the submitted proposal (`Second-Line_Midterm_Proposal_APA (1).pdf`) |
|---|---|
| 1,035 | p. 21, Results: "The monitors detected every ground-truth violation with no false alarms, including all 1,035 violations committed by the shortcut policy with controls off" |
| 729 | p. 23, Table 6 "Effect of Controls on Scripted Agent Policies": Shortcut · Off · *Harmful actions executed* 729 · Detected 100.0% · Correct 52.6% |

- **Likely explanation (not proven):** the two numbers count different units. 1,035 is *violations*, meaning invariant breaches the monitors detected. 729 is *harmful actions executed*. One shortcut action can breach several invariants at once. A suspense plug that also closes a break without evidence, for example, breaks both I3/I9 and I5. 1,035 / 729 ≈ 1.42 violations per harmful action is consistent with that, but the original PoC code and logs, which hold the event definitions, are not in the repository or on Kunal's machine. The only copies found are the proposal itself and a later snapshot of this repo.
- **What the report does:** it cites 729 as harmful actions executed, and 1,035 as invariant violations detected, each labelled `POC-REPORTED` with this note. Neither is used as a denominator for any new claim (§14 MET rules).
- **To resolve it:** find the PoC run logs, or rerun the PoC from its seed if the code is recovered, and count both units directly.

## 2. ISO 20022 / T2S settlement reason codes (§5 B1/B7, RSK-15)
Sources:
- ECB T2S Programme Office, *Insights on multiple statuses in a status notification*. This is bibliography #12 (see §4).
- ECB T2S change requests T2S-0355-URD and T2S-0621-SYS (ecb.europa.eu/paym/target/t2s/governance/pdf/crg/…).
- The ISO 20022 / SWIFT MT548 pages (iso20022.org/15022/uhb/…) refused automated retrieval (HTTP 403). Om or Kunal can open them manually if a second source is wanted.

| code | T2S meaning (ECB slides) | status | notes for the factory |
|---|---|---|---|
| LACK | Lack of securities | **RESOLVED** | Raised on the *delivering* leg (T2S-0355-URD: "normally only occurs on the delivering leg") |
| MONY | Insufficient money | **RESOLVED** | Raised on the *paying* leg |
| CLAC | Counterparty insufficient securities | **RESOLVED** | Raised to the receiver when the counterparty can't deliver. T2S-0355-URD lists CLAC, CMON, LACK, LINK and MONY as the only provision-check values. |
| CMON | Counterparty insufficient money | **RESOLVED** | Raised to the deliverer when the counterparty can't pay |
| LATE | Market deadline missed | **RESOLVED** | §5 proposed it for B1. It's a pending/failing reason; the factory doesn't emit it yet |
| CYCL | not found in any T2S source checked | **UNRESOLVED** | Remove it from the curated snapshot (`data/reference/iso20022/`, KG-02) or keep `verify: true` |

- **CORRECTED, B7 generator (KG-04 #57):** the factory's trades are all **buys**. On a buy the bank pays cash and receives securities, so the only codes that fit are **MONY** (our cash shortfall, routed to TREASURY) and **CLAC** (the counterparty can't deliver, routed to OPERATIONS). The generator currently also draws LACK and CMON, which belong to the other leg. Fix it in #57, and in the KG-02 snapshot (#56) set `verify: false` with the ECB citation for these five codes.
- One Swift MT549 page found in a search describes CLAC differently, as an India-specific clearing-house settlement-date mismatch. That is a different MT549 status qualifier, not the T2S pending reason. The ECB definitions above are the ones the project uses.

## 3. BIC ↔ LEI caveats (§6, B8)
**RESOLVED.**
- GLEIF and Swift publish an open-source **BIC-to-LEI relationship file**: a certified mapping, in CSV, under a licence, published since February 2018. Sources: gleif.org/en/lei-data/lei-mapping/download-bic-to-lei-relationship-files and the GLEIF/Swift press release of 2018-02-08.
- That file only covers BICs that belong to legal entities or foreign branches (about 45k of about 130k BICs per trade-press reporting; verify the figure before citing it). It maps *identifiers*. It says nothing about settlement accounts or standing settlement instructions.
- The project's caveat therefore holds: **an LEI or a BIC↔LEI pair is not a settlement account and doesn't validate an SSI**. The project uses no BIC↔LEI mapping at all. B8's SSIs, BICs and accounts are synthetic (KG-04 decision K5, as built), and the GLEIF snapshot is used only as entity-ID grounding.

## 4. References (§24.1, the 34 submitted entries, plus the §24 additions)
Method:
- Every URL and DOI was resolved over HTTP.
- DOIs that refuse automated access (ACM, SAGE: HTTP 403) were confirmed through Crossref metadata (title, year, venue, pages).
- arXiv IDs were confirmed through the arXiv API (title, first-version date).
- Selected content claims were checked against the source; the quotes are below.

| # | reference | status |
|---|---|---|
| 1 | Anthropic 2024, Introducing MCP | RESOLVED (200) |
| 2 | Assefa et al. 2020, ICAIF, doi 10.1145/3383455.3422554 | RESOLVED (Crossref: "Generating synthetic data in finance", 2020, ICAIF '20). Crossref gives pp. 1–8; the citation's "Article 44" is the ACM article number, and both are fine |
| 3 | BCBS 239 (2013) | RESOLVED (200) |
| 4 | Bhagwatkar et al. 2025, arXiv 2510.05244 | RESOLVED (arXiv title matches, 2025-10-06) |
| 5 | Fed H.10 | RESOLVED (200; KG-02 snapshot taken 2026-11-20) |
| 6 | Fed/OCC 2011, SR 11-7, …/srletters/sr1107a1.pdf | **CORRECTED.** The URL is a 404, and sr1107.pdf and sr1107.htm are 404 too. **SR 11-7 was superseded on 2026-04-17 by SR 26-2, "Revised Guidance on Model Risk Management"** (Fed, OCC and FDIC): https://www.federalreserve.gov/supervisionreg/srletters/sr2602.htm, which says it "supersedes and replaces SR letter 11-7". Cite SR 26-2 for current guidance, and SR 11-7 only as historical, with no live URL |
| 7 | Debenedetti et al. 2025 (CaMeL), arXiv 2503.18813 | RESOLVED |
| 8 | Debenedetti et al. 2024 (AgentDojo), arXiv 2406.13352 | RESOLVED |
| 9 | Duco reconciliation | RESOLVED (200; vendor page, no endorsement) |
| 10 | Eberhardt 2025, FINOS AIGF v2.0 blog | RESOLVED (200) |
| 11 | ECB euro reference rates | RESOLVED (200; KG-02 snapshot) |
| 12 | ECB T2S, multiple statuses slides | RESOLVED (200). This is the primary source for §2 above |
| 13 | FINRA 2026 oversight report | RESOLVED (200) |
| 14 | Gebru et al. 2021, Datasheets for datasets, CACM 64(12) 86–92 | RESOLVED (Crossref) |
| 15, 16 | GLEIF access & use; open data | RESOLVED (200) |
| 17 | JPMorgan Chase synthetic data | RESOLVED (200; access to the data is not guaranteed, §6) |
| 18 | Krakovna et al. 2020, Specification gaming | RESOLVED (200) |
| 19 | Kwon et al. 2023, PagedAttention / vLLM, arXiv 2309.06180 | RESOLVED |
| 20 | Mitchell et al. 2019, Model cards, FAT* 220–229 | RESOLVED (Crossref) |
| 21 | NIST AI 100-1 (2023) | RESOLVED (doi resolves; title matches) |
| 22 | NIST AI 600-1 (2024) | RESOLVED (doi resolves; Crossref title truncated, year matches) |
| 23 | Northeastern RC, Containers on Explorer | RESOLVED (200) |
| 24 | OCC Bulletin 2026-13 | RESOLVED (200, both the occ.gov and www.occ.gov forms). The §24 claim is **confirmed**: "Generative AI and agentic AI models are novel and rapidly evolving … they are not within the scope of this guidance" |
| 25 | OWASP LLM06:2025 Excessive agency | RESOLVED (200) |
| 26 | Parasuraman & Manzey 2010, Human Factors 52(3) 381–410 | RESOLVED (Crossref) |
| 27 | Rebedea et al. 2023, NeMo Guardrails, EMNLP demos 431–445 | RESOLVED |
| 28 | Richardson 2018, *Microservices Patterns* (book, no URL) | UNRESOLVED (no identifier to check; add the ISBN if it is cited) |
| 29 | Scheurer et al. 2023, arXiv 2311.07590 | RESOLVED |
| 30 | Smartstream 2026-09-23 press release | RESOLVED (200; press release, cite as vendor claims) |
| 31 | Son 2026, CNBC, Goldman Sachs / Anthropic | RESOLVED (200) |
| 32 | Wu et al. 2023, BloombergGPT, arXiv 2303.17564 | RESOLVED |
| 33 | Yao et al. 2024, τ-bench, arXiv 2406.12045 | RESOLVED. The §24 claim is **confirmed**: the abstract says "We also propose a new metric (pass^k)" |
| 34 | Zhan et al. 2024, InjecAgent, arXiv 2403.02691 / ACL Findings doi 10.18653/v1/2024.findings-acl.624, pp. 10471–10506 | RESOLVED. The §24 claim is **confirmed**: "1,054 test cases" |

§24 industry items:
- JPMorgan *Securing the next generation of AI agents*: RESOLVED (200).
- MCP 2026-07-28 release notes: RESOLVED (200).
- FINOS AIGF repository: RESOLVED (200).
- FINOS AIGF issue #337: RESOLVED, and still **open** as of 2026-11-20 (opened 2026-07-08, "signed, independently verifiable decision receipts"). It stays described as an open proposal, not an adopted standard.

## 5. Follow-ups this file creates
- [ ] #57 (KG-04): B7 draws only MONY (→ TREASURY) or CLAC (→ OPERATIONS) for buys.
- [ ] #56 (KG-02): set `verify: false` with the ECB citations for LACK, MONY, CLAC and CMON, add LATE, and drop CYCL (or keep it `verify: true`).
- [ ] Report (SH-15): cite SR 26-2 rather than SR 11-7; carry 1,035 and 729 as separate `POC-REPORTED` claims with §1's note; add an ISBN for #28.
