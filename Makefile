# Second-Line 2.0 task runner. Targets that print TODO(<TASK>) are not built yet — that task builds them.
# Recipes are TAB-indented. Works with GNU make 3.81 (macOS default) and 4.x (WSL/CI).
SHELL := /bin/bash
PY ?= python3
PROFILES ?= core
# Intended (OM-01): COMPOSE = docker compose -f infra/compose/docker-compose.yml $(foreach p,$(PROFILES),--profile $(p))

define todo
@echo "TODO($(1)): '$@' is not built yet -> python3 scripts/board.py show $(1)"; exit 1
endef

.DEFAULT_GOAL := help
.PHONY: help board-next board-check trace spec-check spec-split ctx kit-test kit-check hpc-help \
 bootstrap up down ps logs reset db-shell lint test codegen codegen-java codegen-py contracts-check \
 test-ledger test-gateway test-mcp test-policy test-py test-agent test-factory test-eval test-supervisor test-console \
 test-int test-sec test-redteam test-chaos test-load leakage-check refdata-verify \
 factory factory-all run-one pilot campaign analyze replay verify-chain demo-up demo-seed demo-run demo-test

help: ## List targets
	@grep -E '^[a-zA-Z0-9_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-16s %s\n", $$1, $$2}'

# ---- kit (works today) -------------------------------------------------------
board-next: ## Next task card(s) for the owner in CLAUDE.local.md / SL_OWNER
	@$(PY) scripts/board.py next
board-check: ## Validate boards + coverage of every spec ID
	@$(PY) scripts/board.py check
trace: ## Regenerate docs/team/TRACEABILITY.md and the PLAN.md effort table
	@$(PY) scripts/board.py trace --write && $(PY) scripts/board.py summary --write
spec-check: ## Spec shards still match MASTER_SPEC.md
	@$(PY) scripts/split_spec.py --check
spec-split: ## Regenerate spec shards (only after an approved spec change)
	@$(PY) scripts/split_spec.py
ctx: ## Always-loaded Claude context budget
	@$(PY) scripts/ctx_budget.py --max 3500
KIT_TESTS ?= tests/security
kit-test: ## Kit guardrail tests: hpc.sh, hooks, skills gate (OM-26)
	@out=$$($(PY) -m unittest discover -s $(KIT_TESTS) -p 'test_om_26_*.py' 2>&1) || { echo "$$out"; exit 1; }; echo "$$out" | tail -1
kit-check: spec-check board-check skills-lint ctx kit-test ## All kit checks (same as CI)
hpc-help: ## Explorer vLLM runbook pointer
	@@sed -n '1,25p' docs/setup/EXPLORER-HPC.md

# ---- platform / stack (Om) -----------------------------------------------------
bootstrap: ## One-time dependency install (OM-01 + KG-01)
	$(call todo,OM-01)
up: ## Start profiles, e.g. make up PROFILES="core app" (core app events obs ui chaos)
	$(call todo,OM-01)
down: ## Stop the stack
	$(call todo,OM-01)
ps: ## Service health
	$(call todo,OM-01)
logs: ## Tail one service: make logs SVC=ledger TAIL=50
	$(call todo,OM-01)
reset: ## Drop + reload a namespace: make reset NS=<id>
	$(call todo,OM-04)
db-shell: ## psql into the dev database
	$(call todo,OM-01)
lint: ## All linters
	$(call todo,OM-01)
test: ## All unit suites (quiet)
	$(call todo,OM-01)
codegen: ## Regenerate Java + Python (+ TS) types from packages/contracts
	$(call todo,SH-02)
codegen-java: ## Java types
	$(call todo,OM-02)
codegen-py: ## Python sl_contracts models
	$(call todo,KG-01)
contracts-check: ## Validate schemas + examples
	$(call todo,SH-02)
test-ledger: ## Ledger unit + property tests
	$(call todo,OM-03)
test-gateway: ## Gateway tests
	$(call todo,OM-05)
test-mcp: ## MCP adapter contract tests
	$(call todo,OM-06)
test-policy: ## opa test
	$(call todo,OM-10)
test-int: ## Cross-service integration (Testcontainers)
	$(call todo,OM-13)
test-sec: ## Security tests T-SEC-*
	$(call todo,OM-07)
test-chaos: ## Chaos matrix (Toxiproxy)
	$(call todo,OM-18)
test-load: ## k6 load test
	$(call todo,OM-19)
test-console: ## Console unit + Playwright
	$(call todo,OM-21)
demo-up: ## Demo stack
	$(call todo,OM-23)
demo-seed: ## Seed demo cases
	$(call todo,OM-23)
demo-run: ## Run the demo script path
	$(call todo,OM-23)
demo-test: ## Demo smoke test
	$(call todo,OM-23)

# ---- intelligence / evidence (Kunal) ---------------------------------------------
test-py: ## All Python suites (quiet)
	$(call todo,KG-01)
test-agent: ## Agent tests
	$(call todo,KG-08)
test-factory: ## Factory tests
	$(call todo,KG-03)
test-eval: ## Grader / runner / stats tests
	$(call todo,KG-06)
test-supervisor: ## Monitor tests
	$(call todo,KG-11)
test-redteam: ## Platform red-team suite by family
	$(call todo,KG-14)
leakage-check: ## Canary + truth-field scan
	$(call todo,KG-05)
refdata-verify: ## Re-hash reference snapshots
	$(call todo,KG-02)
factory: ## Generate scenarios: make factory SPLIT=dev N=40
	$(call todo,KG-03)
factory-all: ## Generate dev + eval + blind
	$(call todo,KG-04)
run-one: ## One run: make run-one SCN=<id> CONTROLS=off|monitor|full STRATEGY=llm|rules
	$(call todo,SH-07)
pilot: ## 20-scenario pilot
	$(call todo,KG-17)
campaign: ## Campaign: make campaign CFG=<yaml> SHARD=1/2
	$(call todo,KG-18)
analyze: ## Stats + figures: make analyze CAMPAIGN=<id>
	$(call todo,KG-19)
replay: ## Replay: make replay RUN=<id> MODE=action|live
	$(call todo,KG-20)
verify-chain: ## Verify a run's receipt chain: make verify-chain RUN=<id>
	$(call todo,KG-12)

# ---- skills gate (run install in YOUR terminal: plugins execute with your privileges) -----
skills-install: ## Install + verify your Claude plugins/skills: make skills-install [CARD=OM-06] [BIN=1]
	@$(PY) scripts/skills.py install $(CARD) $(if $(BIN),--with-binaries)
skills-check: ## Verify the skills gate: make skills-check [CARD=OM-06]
	@$(PY) scripts/skills.py check $(CARD)
skills-list: ## What you need and why
	@$(PY) scripts/skills.py list
skills-update: ## Re-pin vendored skills to upstream HEAD (commit the lock in a PR)
	@$(PY) scripts/skills.py install --update
skills-lint: ## Manifest + board skill references (CI)
	@$(PY) scripts/skills.py lint

# ---- Explorer HPC (your SSH session — Claude never handles credentials) ----------------
hpc-check: ## Explorer reachable without prompts
	@bash scripts/hpc.sh check
hpc-up: ## Submit infra/hpc/vllm.sbatch
	@bash scripts/hpc.sh up
hpc-status: ## Job state
	@bash scripts/hpc.sh status
hpc-tunnel: ## localhost:8001 -> compute node:8000
	@bash scripts/hpc.sh tunnel
hpc-health: ## GET /v1/models through the tunnel
	@bash scripts/hpc.sh health
hpc-logs: ## Tail the job log: make hpc-logs TAIL=100
	@bash scripts/hpc.sh logs
hpc-down: ## Cancel the job + close the tunnel
	@bash scripts/hpc.sh down
