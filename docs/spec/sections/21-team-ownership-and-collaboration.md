## 21. TEAM OWNERSHIP AND COLLABORATION

**Proposal-assumed split (confirm with both teammates):** Om — Spring Boot ledger, DB/outbox, API/security/OPA/Redis/Kafka, monitoring/observability, frontend/replay integration. Kunal — LangGraph/LLM/MCP, scenario factory, adversarial cases, evaluation protocol, model serving/experiments, statistics. **Shared:** domain schema, action/evidence contract, truth grading semantics, system tests, architecture reviews, financial validity review, final report, demo. This split was originally a working assumption, **not a confirmed allocation**.

**Ways of working:** Short module-length iteration, runnable E2E vertical slice per iteration, ADR before changes to trust boundaries, code review cross-ownership, PR template with threat/experiment implications, shared contract tests. Git branches/CI and definitions of done based on evidence, not number of tools added.

**Documentation artifacts:** `README.md`, `ARCHITECTURE.md`, `ADR/`, `docs/domain.md`, `docs/security-threat-model.md`, `docs/data-governance.md`, `docs/experiment-preregistration.md`, `docs/experiment-amendments.md`, `docs/evaluation-results.md`, `docs/demo-script.md`, `docs/runbooks.md`, OpenAPI/MCP schemas, dataset datasheet, model card per tested config, risk-control matrix, and paper/report. These can be generated later; this one master file is the source for creating them, not proof they already exist.

**Repository outline (recommended, not mandatory):**

```text
second-line/
  apps/console/                    # Next.js/TypeScript UI
  services/ledger/                 # Java/Spring Boot finance service
  services/agent/                  # Python/LangGraph + MCP adapter
  services/gateway/                # auth/policy/control plane
  services/supervisor/             # event consumption, invariants
  packages/contracts/              # OpenAPI, JSON schemas, event schemas
  packages/scenario-factory/       # synthetic causal worlds + oracle (access separated)
  packages/evaluation/             # scorers, stats, baselines, replay
  infra/compose/ infra/opa/ infra/observability/
  experiments/                     # prereg, locked configs, manifests, aggregate results
  tests/unit/ tests/integration/ tests/property/ tests/security/ tests/chaos/
  docs/adr/ docs/datasheets/ docs/model-cards/ docs/demo/
  Makefile .github/workflows/ README.md
```

**Risk-to-control evidence crosswalk (minimum validation report schema):**

| Governance theme | Second-Line implementation | Required evidence |
|---|---|---|
| Independent validation / effective challenge | Oracle-separated harness, blind set, scoped recommendation | Frozen scorecard, error analysis and reviewer signoff |
| Data accuracy, integrity and lineage (BCBS context) | Versioned snapshots, transactional ledger/outbox, invariant checks | Source hashes, ledger journal IDs, alert records |
| NIST AI risk lifecycle / FINOS agentic controls | Risk-classified test matrix, preventative/detective controls | Risk→control→test→result mappings |
| Least privilege and mediation (OWASP) | MCP gateway/OPA and downstream auth rechecks | Allowed/denied tool receipts and bypass tests |
| Documentation and transparency | Datasheets, model cards, action decision receipts | Config manifest and limitation statements |
| Human oversight / automation bias | Maker/checker and evidence-required approvals | Reviewer identity, reason code, approved action digest |
| Privacy/data minimization | Synthetic world, limited traces and scope | Data provenance, secret scans and access tests |

**Ethics/governance:** Privacy by synthetic data, no real identities/keys in artifacts, risk controls with human oversight and limited authority, benchmark release with defensive context, no exaggerated regulation or commercial certification claims. Map concrete tests/evidence to NIST AI RMF (Govern/Map/Measure/Manage), NIST GenAI Profile, FINOS AIGF agentic risks, OWASP excessive agency and relevant BCBS data quality principles; **mapping does not mean formal compliance**.

