## 22. RISKS, BLOCKERS AND FALLBACKS

| Risk | Signal | Mitigation / fallback |
|---|---|---|
| RSK-01 Integration overrun | No end-to-end real LLM by M-2 | Freeze tools/interfaces; reduce UI before dropping core controls |
| RSK-02 Unrealistic simulator | Correct root cause trivially leaked or impossible | Causal generation, hidden truth, golden cases, blind/external review |
| RSK-03 LLM never violates under pressure | Low observed failure count | Report safe result; test known difficult legitimate scenarios; **do not fabricate attacks or outcomes** |
| RSK-04 LLM costs / HPC Slurm waiting | Queued GPUs/token overbudget | API or small local model for E2E, resume by manifests, pre-budget runs, non-HPC demo |
| RSK-05 H2 p99 fails | Network/OPA/review overhead | Separate policy latency from total action; optimize/cache safe decisions; report failed H2 honestly |
| RSK-06 H3 precision fails | Wide clustered CIs | Treat as negative research finding; transparent additional exploration if more independent scenarios |
| RSK-07 Control blocks legitimate resolution | Task success collapses | Assess utility-vs-risk, safe escalation, pre-commit selective enforcement not blanket blocking |
| RSK-08 Kafka/Redis failure causes wrong state | Lost/duplicated business changes | Durable Postgres truth, outbox, DB keys, fail closed on critical path |
| RSK-09 Audit not independently verifiable | Only local chain, no anchor | Document limitation; add signed checkpoints when time permits |
| RSK-10 Model judged by itself | Fabricated or unsupported explanations pass | Independent canonical truth/evidence verification; model narrative non-authoritative |
| RSK-11 Evaluator biased by self-generated tasks | Overly rosy benchmark | Dev/frozen/blind sets, external review, adversarial OOD cases |
| RSK-12 Scope creep from industry buzzwords | New tools without measured benefit | Maintain P0/P1/P2 and decision register; defer Kubernetes, multi-agent and generic RAG |
| RSK-13 Demo dependency outage | Live GPU/API/network unavailable | Local seeded Docker environment + clearly labeled deterministic trace playback |
| RSK-14 Research vs product conflation | Rebranded original H1–H3 post-hoc | Keep prereg + amendments + exploration separate; detailed outcome provenance |
| RSK-15 Domain code/reference error | Unverified codes/mappings | Authoritative source check before claiming ISO/bank realism |

**Time/cost feasibility gate:** Before committing to all 3,300 model runs, measure end-to-end input/output tokens, total tool calls, model rate limits, cost per run, GPU hours and failure/retry rate on small stratified pilot. The original 48M token estimate is approximate input-only. Data collection is more valuable when informative and reproducible, not only larger.

