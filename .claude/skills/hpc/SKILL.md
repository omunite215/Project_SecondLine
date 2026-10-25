---
name: hpc
description: Operate the Explorer vLLM endpoint through make hpc-* using the human's own SSH session — never credentials.
disable-model-invocation: true
argument-hint: "check|up|status|tunnel|health|logs|down"
allowed-tools:
  - 'Bash(python3 "${CLAUDE_PROJECT_DIR}/scripts/board.py" *)'
  - 'Bash(python3 "${CLAUDE_PROJECT_DIR}/scripts/skills.py" *)'
  - 'Bash(python3 "${CLAUDE_PROJECT_DIR}/scripts/ctx.py" *)'
---
!`python3 "${CLAUDE_PROJECT_DIR}/scripts/ctx.py" hpc`

- Never ask for, read or handle passwords, Duo codes or SSH keys. If the check above failed, tell the human to run `ssh explorer true` in their own terminal (opens the ControlMaster session for 8 h — docs/setup/EXPLORER-HPC.md), then retry.
- Serving session: `make hpc-up` → `make hpc-status` until RUNNING → `make hpc-tunnel` → `make hpc-health` → work with OPENAI_BASE_URL=http://localhost:8001/v1 → `make hpc-down` when finished (GPU hours are shared).
- Record image digest, model id + revision, vLLM flags and GPU type in experiments/manifests/serving.json (KG-10).
