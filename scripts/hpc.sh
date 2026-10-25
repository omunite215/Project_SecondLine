#!/usr/bin/env bash
# Explorer HPC helpers (SH-19 / KG-10). Uses YOUR ssh config alias (default: explorer).
# BatchMode=yes: ssh never prompts. Without a key/agent/ControlMaster session it fails fast,
# so Claude Code can run these targets without ever seeing a password, Duo prompt or key.
set -euo pipefail
cd "$(dirname "$0")/.."
HOST="${SL_HPC_HOST:-explorer}"
PORT="${SL_HPC_PORT:-8001}"
STATE=".hpc"; JOB_FILE="$STATE/job_id"
SBATCH="${SL_HPC_SBATCH:-infra/hpc/vllm.sbatch}"
REMOTE_DIR='~/second-line-hpc'
SSH=(ssh -o BatchMode=yes -o ConnectTimeout=15 "$HOST")
die() { echo "hpc: $*" >&2; exit 1; }
job() { [ -s "$JOB_FILE" ] || die "no job recorded — run: make hpc-up"; cat "$JOB_FILE"; }
case "${1:-help}" in
  check)
    "${SSH[@]}" 'echo "ok host=$(hostname) user=$USER"; command -v sbatch >/dev/null && echo slurm=ok || echo slurm=missing' \
      || die "can't reach '$HOST' without a prompt. In YOUR terminal run: ssh $HOST true   (see docs/setup/EXPLORER-HPC.md)" ;;
  up)
    [ -f "$SBATCH" ] || die "$SBATCH missing — copy infra/hpc/vllm.sbatch.template and fill it in (KG-10)"
    if grep -q '<' "$SBATCH"; then die "$SBATCH still has <placeholders>"; fi
    mkdir -p "$STATE"
    "${SSH[@]}" "mkdir -p $REMOTE_DIR /scratch/\$USER/sl-logs"
    scp -q -o BatchMode=yes "$SBATCH" "$HOST:$REMOTE_DIR/vllm.sbatch"
    out=$("${SSH[@]}" "cd $REMOTE_DIR && sbatch --parsable vllm.sbatch")
    echo "${out%%;*}" > "$JOB_FILE"; echo "submitted job $(cat "$JOB_FILE")" ;;
  status)
    j=$(job); "${SSH[@]}" "squeue -j $j -o '%.12i %.10P %.10T %.10M %R' 2>/dev/null || sacct -j $j --format=JobID,State,Elapsed -n" ;;
  tunnel)
    j=$(job); node=$("${SSH[@]}" "squeue -j $j -h -o %N"); [ -n "$node" ] || die "job $j has no node yet (make hpc-status)"
    ssh -o BatchMode=yes -o ExitOnForwardFailure=yes -f -N -L "$PORT:$node:8000" "$HOST" && echo "tunnel: localhost:$PORT -> $node:8000" ;;
  health)
    curl -fsS "http://localhost:$PORT/v1/models" | head -c 400; echo ;;
  logs)
    j=$(job); "${SSH[@]}" "tail -n ${TAIL:-50} /scratch/\$USER/sl-logs/vllm-$j.out" ;;
  down)
    j=$(job); "${SSH[@]}" "scancel $j"; rm -f "$JOB_FILE"; pkill -f "ssh .*-L $PORT:" 2>/dev/null || true; echo "cancelled $j; tunnel closed" ;;
  *) echo "usage: scripts/hpc.sh check|up|status|tunnel|health|logs|down"; exit 2 ;;
esac
