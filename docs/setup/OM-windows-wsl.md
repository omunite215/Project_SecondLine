# Om — Windows 11 + WSL2 setup
ASUS Vivobook Pro 15 OLED · Ryzen 7 5800H (8C/16T) · 16 GB RAM · RTX 3050 Laptop (4 GB VRAM — confirm with `nvidia-smi`).
Everything runs inside WSL2 Ubuntu. Windows hosts only the VS Code window, Docker Desktop and the NVIDIA driver. The hooks, skills and gate need bash + python3, so run Claude Code inside WSL.

## 1. WSL2 with a memory cap
1. PowerShell (admin): `wsl --install -d Ubuntu-24.04`; then inside Ubuntu `sudo apt update && sudo apt upgrade`.
2. Create `C:\Users\<you>\.wslconfig` with:
   ```ini
   [wsl2]
   memory=10GB
   processors=12
   swap=8GB
   ```
3. Run `wsl --shutdown` to apply it.

This leaves ~6 GB for Windows and the VS Code UI. Docker Desktop's WSL2 backend lives inside this cap.

## 2. Repo
`git clone https://github.com/omunite215/Project_SecondLine.git ~/code/Project_SecondLine`. Keep it on the WSL ext4 disk, never `/mnt/c` (slow I/O, broken file watchers).

## 3. Toolchain (inside WSL)
- `sudo apt install -y build-essential make git gh openssh-client ripgrep unzip curl python3 python3-venv`
- Java 21 via SDKMAN (`sdk install java 21-tem`); Python via uv; Node 22 LTS via fnm, then `corepack enable` (pnpm). With fnm, global npm installs need no sudo.
- Docker Desktop: WSL2 backend + integration for Ubuntu-24.04; check with `docker run --rm hello-world` inside WSL.
- GPU: install only the Windows NVIDIA driver; `nvidia-smi` must work inside WSL.

## 4. Claude Code + the skills gate
1. CLI inside WSL: `curl -fsSL https://claude.ai/install.sh | bash`, then run `claude` once to log in.
2. VS Code on Windows → "WSL" extension → *Connect to WSL* → open `~/code/Project_SecondLine` → accept the recommended extensions (including Claude Code).
3. Personal files:
   ```bash
   cp docs/ai/CLAUDE.local.md.om.example CLAUDE.local.md
   cp .claude/settings.local.json.om.example .claude/settings.local.json
   ```
4. `gh auth login` — in your terminal, never through Claude.
5. `make skills-install BIN=1`. It installs pyright, typescript-language-server and jdtls (keep `~/.local/bin` on PATH), registers the trailofbits and anthropics/skills marketplaces, and installs your plugins.
6. `make skills-check` must print GREEN. Then restart VS Code (or the Claude session) and confirm the session opens with `[skills] GREEN`.

## 5. Local LLM (smoke tests only)
Install Ollama inside WSL (`curl -fsSL https://ollama.com/install.sh | sh`; it uses CUDA through WSL). Pull one ≤4B instruct model whose page lists tool calling. It's for plumbing tests of the gateway/MCP path — never an experiment arm.

## 6. Running the stack on 16 GB (approximate — measure with `docker stats`)
| profiles | adds roughly |
|---|---|
| core (postgres, redis, opa) | 0.6 GB |
| + app (ledger, gateway, mcp-adapter) | +1.5 GB |
| + events (kafka, supervisor) | +1.0 GB |
| + obs (otel, jaeger, prometheus, grafana) | +1.0 GB |
| + ui (console dev server) | +0.8 GB |

VS Code server + the Java language server + a Gradle daemon add ~2–3 GB more. Start only what the task needs.
- JVM services: `-Xmx512m`.
- `gradle.properties`: `org.gradle.jvmargs=-Xmx1g`, `org.gradle.workers.max=4`.
- If it still gets tight, host the Docker stack on a machine with more RAM.

## 7. Explorer HPC + GitHub admin
- `docs/setup/EXPLORER-HPC.md` — you hold the account.
- `docs/setup/GITHUB.md` — rulesets, secrets, PR approvals.

## 8. Campaign shards
Before an overnight shard: plug in, set Windows power mode to "Best performance", disable sleep, and set the MyASUS fan profile to "Performance". Then start the shard with the campaign runner (PLANNED: KG-15 builds `campaign`; `make help` lists it once implemented).
