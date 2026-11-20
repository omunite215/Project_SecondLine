# Reference-data inputs (generated from MANIFEST.json by `scripts/refdata.py`; KG-02 → KG-22 datasheet)

Do not edit by hand. Synthetic-world inputs only: public reference data, no client data.

## ecb@2026-11-20

- source: ecb · retrieved_at: 2026-11-20T02:43:26Z
- license: ECB statistics: free reuse with source acknowledgement (https://www.ecb.europa.eu/home/disclaimer/html/index.en.html)
- needs verification (SH-13): yes
- url: https://data-api.ecb.europa.eu/service/data/EXR/D.USD+GBP+CHF+JPY.EUR.SP00.A?format=csvdata&startPeriod=2026-01-02&endPeriod=2026-11-19
- coverage gap: no rates on weekends or TARGET holidays
- coverage gap: pairs USD, GBP, CHF, JPY per EUR only; window 2026-01-02..2026-11-19
- caveat: information-only reference rates, not executable transaction prices (§6)
- caveat: concertation 14:15 CET; published around 16:00 CET
- caveat: raw.csv stored with LF line endings (normalized from the download)

| file | rows | sha256 |
|---|---|---|
| ecb/2026-11-20/rates.json | 908 | `sha256:1710f1035c77…` |
| ecb/2026-11-20/raw.csv |  | `sha256:1be7a6d2ccf7…` |

## gleif@2026-11-20

- source: gleif · retrieved_at: 2026-11-20T02:43:32Z
- license: CC0 1.0 (GLEIF LEI data) (https://www.gleif.org/en/meta/lei-data-terms-of-use)
- needs verification (SH-13): no
- url: https://api.gleif.org/api/v1/lei-records?filter%5Bentity.legalAddress.country%5D=US&filter%5Bregistration.status%5D=ISSUED&sort=lei&page%5Bsize%5D=100&page%5Bnumber%5D=1
- url: https://api.gleif.org/api/v1/lei-records?filter%5Bentity.legalAddress.country%5D=GB&filter%5Bregistration.status%5D=ISSUED&sort=lei&page%5Bsize%5D=100&page%5Bnumber%5D=1
- url: https://api.gleif.org/api/v1/lei-records?filter%5Bentity.legalAddress.country%5D=DE&filter%5Bregistration.status%5D=ISSUED&sort=lei&page%5Bsize%5D=100&page%5Bnumber%5D=1
- url: https://api.gleif.org/api/v1/lei-records?filter%5Bentity.legalAddress.country%5D=CH&filter%5Bregistration.status%5D=ISSUED&sort=lei&page%5Bsize%5D=100&page%5Bnumber%5D=1
- url: https://api.gleif.org/api/v1/lei-records?filter%5Bentity.legalAddress.country%5D=JP&filter%5Bregistration.status%5D=ISSUED&sort=lei&page%5Bsize%5D=100&page%5Bnumber%5D=1
- coverage gap: first 100 ISSUED LEIs by LEI per US, GB, DE, CH, JP; not representative
- coverage gap: no BIC or settlement-account mapping fetched
- coverage gap: 1 SOLE_PROPRIETOR record(s) excluded (natural persons)
- caveat: an LEI identifies a legal entity, not a settlement account (§6)

| file | rows | sha256 |
|---|---|---|
| gleif/2026-11-20/lei_subset.json | 499 | `sha256:c9b0dfaabb20…` |

## h10@2026-11-20

- source: h10 · retrieved_at: 2026-11-20T02:43:26Z
- license: Federal Reserve Board statistical release; public data, cite the Board (https://www.federalreserve.gov/data.htm)
- needs verification (SH-13): yes
- url: https://www.federalreserve.gov/datadownload/Output.aspx?rel=H10&series=60f32914ab61dfab590e0e470153e3ae&lastobs=260&from=&to=&filetype=csv&label=include&layout=seriescolumn
- coverage gap: window 2026-01-02..2026-11-13: H.10 is published weekly with a lag
- coverage gap: 44 'ND' (no data) observations in the raw download dropped, e.g. US holidays
- coverage gap: EUR and GBP quoted as USD per unit; CHF and JPY as units per USD
- caveat: noon buying rates in New York: different methodology and timing from ECB (§6)
- caveat: compare with ECB only on aligned_with_ecb.json dates; never exchangeable
- caveat: raw.csv stored with LF line endings (normalized from the download)

| file | rows | sha256 |
|---|---|---|
| h10/2026-11-20/aligned_with_ecb.json | 215 | `sha256:191567f6f231…` |
| h10/2026-11-20/rates.json | 872 | `sha256:105b9c69a03d…` |
| h10/2026-11-20/raw.csv |  | `sha256:60c127f56b58…` |

## iso20022@2026-11-20

- source: iso20022 · retrieved_at: 2026-11-20T03:26:00Z
- license: curated from public ISO 20022 / ECB T2S documentation (codes and meanings only) (https://www.iso20022.org/catalogue-messages/additional-content-messages/external-code-sets)
- needs verification (SH-13): no
- url: https://www.ecb.europa.eu/paym/target/t2s/profuse/shared/pdf/insights_on_multiple_statuses_in_a_status_notification.pdf
- url: https://www.iso20022.org/catalogue-messages/additional-content-messages/external-code-sets
- coverage gap: curated, not fetched: pending/failing reason codes used by B1/B7 only
- caveat: meanings confirmed against ECB T2S sources in SH-13 (docs/sources-verification.md)
- caveat: factory trades are buys: only MONY and CLAC apply to B7 (SH-13)

| file | rows | sha256 |
|---|---|---|
| iso20022/2026-11-20/settlement_codes.json | 5 | `sha256:7b884a9554db…` |
