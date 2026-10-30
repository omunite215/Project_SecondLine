# Kunal — macOS setup (MacBook Air, Apple M4, 16 GB)
Record the exact chip and unified memory in docs/team/KUNAL.md and CLAUDE.local.md during SH-01.

## 1. Toolchain
- **Basics:** Homebrew, then `brew install git gh make ripgrep uv`, then Python 3.12 via `uv python install 3.12`.
- **Docker:** Docker Desktop for Apple Silicon. With ≤18 GB unified memory, OrbStack is a lighter drop-in (Testcontainers works with both).
- **Java:** not required — the Java services build inside their Docker images.
- **Node 22 + pnpm:** only if you touch the console. pyright doesn't need it (see below).

## 2. Repo, Claude Code, skills gate
1. Clone: `git clone https://github.com/omunite215/Project_SecondLine.git && cd Project_SecondLine`.
2. CLI: `curl -fsSL https://claude.ai/install.sh | bash`, then run `claude` once to log in.
3. VS Code: start it from a terminal (`code .`) so Homebrew/uv paths reach Claude Code, and accept the recommended extensions.
4. Personal files:
   ```bash
   cp CLAUDE.local.md.kunal.example CLAUDE.local.md
   cp .claude/settings.local.json.kunal.example .claude/settings.local.json
   ```
   Then fill in your chip and RAM.
5. `gh auth login` — in your terminal, never through Claude.
6. `make skills-install BIN=1`. It installs pyright (`uv tool install pyright` if there's no npm), installs superpowers + pyright-lsp, and vendors the LangGraph skills into services/agent/.claude/skills.
7. `make skills-check` must print GREEN. Restart the Claude session and confirm `[skills] GREEN`.

## 3. Local LLM (agent dev loop)
Install Ollama natively — it uses the Metal GPU, which Docker on macOS can't. Pick the model size by unified memory, at Q4:

| unified memory | dev model size |
|---|---|
| 16 GB | 7–8B |
| 18–24 GB | up to ~14B |
| 36 GB+ | ~30B class |

- Native code uses `OPENAI_BASE_URL=http://localhost:11434/v1`.
- Containers use `http://host.docker.internal:11434/v1`.

## 4. Pull requests
- Branch `kunal/<ID>-slug`, then `/finish-task` → `/open-pr`.
- Om reviews, approves and merges.
- You never push to main. Branch protection enforces it.

## 5. Architecture + Explorer
- **Architecture:** you're arm64; CI and Om are amd64. Flag any single-arch image to Om instead of using emulation.
- **Explorer:** file the access request in SH-19 (docs/setup/EXPLORER-HPC.md). Until it's approved, Om runs `make hpc-*`.

## 6. Campaigns
When your machine is the latency reference host, put `system_profiler SPHardwareDataType` in the manifest, stay plugged in and run `caffeinate -dimsu`.
