## 2. HISTORY, TRUTH STATUS AND CHANGE CONTROL

| Label | Meaning | Examples |
|---|---|---|
| `BASELINE-SUBMITTED` | In 2026-09-25 academic proposal; preserve faithfully | RQ1–3/H1–3; 8 break types; 40-dev/200-eval; 3,300 planned model runs; Module 4–7 plan |
| `POC-REPORTED` | Previously reported scripted-prototype findings; **not LLM experiments** | Python+SQLite simulator, four scripted policies, 2,400 scripted runs, graph/table results |
| `ADOPTED-DESIGN` | User approved; proposed engineering design, **not yet implemented** | Pre-commit verifier, causal world, rules baseline, receipts, counterfactual replay, chaos tests, risk console |
| `PLANNED` | Intended work not validated in the supplied materials | Live LangGraph+MCP model, real OPA/Kafka/Spring integration, vLLM cluster runs, dashboards |
| `OPTIONAL/AFTER COURSE` | Explicit extension, not a grading dependency | Other domains, fine-tuning, Kubernetes, second reviewer LLM, large-scale model comparisons |
| `VERIFY` | Needs independent validation/correction | Original PoC inconsistent harm count; bibliographic gaps; domain taxonomy code mappings |

**Known source discrepancy:** Submitted prose says the shortcut policy had **1,035 violations** detected when controls were off; submitted Table 6 reports **729 harmful actions executed** for shortcut/off. These may be different denominators/types but cannot be equated without original code/logs; carry both as distinct `POC-REPORTED` claims until reconciled. Do **not** use the 1,035 value as definitively a count of executed harmful actions.

**Research transparency:** The original proposal uses the word *certify*; product/portfolio language shall say *evaluate; provide evidence to inform a deployment decision*. The 2026 revised interagency model-risk guidance explicitly excludes generative/agentic AI from that guidance's scope; this does **not** imply there are no other applicable governance obligations. Do not describe it as a regulatory vacuum.

**Regulatory/source review:** See `§24` for canonical public links and original academic bibliography. Claims about competitor capabilities or regulatory treatment should be rechecked when used in a final paper or demo.

