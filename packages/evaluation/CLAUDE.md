# packages/evaluation — grader, runner, stats, replay, eval API (owner: Kunal · grader reviewed by Om) — PRIVILEGED
Python · pandas/pyarrow · scipy/statsmodels · FastAPI.
```text
src/sl_eval/grader/    Truth + ns export + action/decision/receipt log → labels (ADR-006)
src/sl_eval/scripted/  oracle / shortcut / retry / sloppy golden drivers (fresh code, §16 concepts)
src/sl_eval/runner/    campaigns, units, manifests, resume, --shard i/n
src/sl_eval/stats/     cluster bootstrap, H1 mixed model, H2 paired, H3 pass^k
src/sl_eval/replay/    action replay + paired live (mandatory mode field)
src/sl_eval/api/       eval API (openapi/eval.yaml) + export builder
```
Commands: `make test-eval` · `make pilot` · `make campaign CFG=… SHARD=1/2` · `make analyze CAMPAIGN=…` · `make replay RUN=… MODE=action|live`
- The grader never treats agent narrative as evidence; ORACLE_MISMATCH is reported, never auto-fixed.
- Rules: .claude/rules/experiment-integrity.md.
