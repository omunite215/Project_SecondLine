# Explorer HPC — access, vLLM serving, Claude Code (SH-19, KG-10)
**No model training in this project.** Fine-tuning is out of scope (§3; §26 is post-course). Explorer only *serves* an open-weight model with vLLM for the bake-off (KG-10), the pilot (KG-17) and the 3,000-run open-weight arm (KG-18). Adding training would be a scope change: ADR + instructor sign-off, and never on eval/blind data.

**Credentials never go through Claude.** Claude only runs `make hpc-*`. Those targets use your own SSH session with `BatchMode=yes`, so ssh never prompts: if no session is open, the command fails fast and tells you to run `ssh explorer true` yourself. `~/.ssh` is deny-listed for Claude.

## 1. Accounts
- Om has access.
- Kunal: submit the Research Computing Access Request in ServiceNow, with the instructor (or a PI) as sponsor, during SH-01. Access can take up to ~24 h after the sponsor approves.
- Until then, Om runs the HPC targets.

## 2. One-time SSH setup (each account holder, in your own terminal)
```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_explorer
ssh-copy-id -i ~/.ssh/id_ed25519_explorer.pub <nu-username>@login.explorer.northeastern.edu   # your NU password, once, here
```
Add to `~/.ssh/config`:
```text
Host explorer
  HostName login.explorer.northeastern.edu
  User <nu-username>
  IdentityFile ~/.ssh/id_ed25519_explorer
  IdentitiesOnly yes
  ControlMaster auto
  ControlPath ~/.ssh/cm-%r@%h-%p
  ControlPersist 8h
  ServerAliveInterval 60
```
1. Test with `ssh explorer hostname`.
2. Then run `make hpc-check`, from Claude Code or a terminal. It should print `ok host=…`.
3. If the cluster still asks for a password or Duo, run `ssh explorer true` once a day in your own terminal. Claude's commands reuse that ControlMaster session for 8 h.

## 3. Serving session
1. **Config (KG-10):** copy `infra/hpc/vllm.sbatch.template` → `infra/hpc/vllm.sbatch`, fill in the partition, GPU, model + revision and tool-call parser, and commit it. It holds no secrets.
2. **Submit:** `make hpc-up` submits the job and records its id in `.hpc/` (gitignored).
3. **Wait:** `make hpc-status` until it shows RUNNING.
4. **Connect:** `make hpc-tunnel` maps localhost:8001 → node:8000, then `make hpc-health` checks it.
5. **Work** with `OPENAI_BASE_URL=http://localhost:8001/v1`.
6. **Stop:** `make hpc-down` when finished — GPU hours are shared.

Record per campaign, in `experiments/manifests/serving.json`: image digest, model id + revision, vLLM flags, GPU type, max_model_len and sampling parameters.

## 4. Who runs what
- The open-weight arm runs on the laptop that holds the tunnel: Om's, until Kunal has an account.
- Keep one latency reference host per campaign (H2).

## 5. Fallback
- If the queue wait is too long, run the pilot on the API arm.
- The demo never depends on Explorer.
- Verify partition names, GPU types, time limits and module names in the RC docs: https://rc-docs.northeastern.edu/en/latest/
