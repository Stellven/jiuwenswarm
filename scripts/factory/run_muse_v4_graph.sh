#!/bin/bash
# First end-to-end run of the Muse demo graph (contract muse-2bit-ttft-v4, preliminary node contracts) on the Spark.
#
#   TASK and FACTORY_HOME are required (no defaults, so a half-set shell never starts the wrong run):
#   TASK=muse-2bit-ttft-v4 FACTORY_HOME=~/muse-demo/graph-v4 SESSION=muse scripts/factory/run_muse_v4_graph.sh ...
#   scripts/factory/run_muse_v4_graph.sh setup            # factory home, owned checkout, task init (once)
#   scripts/factory/run_muse_v4_graph.sh run              # jobq worker + controller in tmux (resume = run again)
#   STEP=1 scripts/factory/run_muse_v4_graph.sh run       # stop at a step checkpoint before every node
#   scripts/factory/run_muse_v4_graph.sh release NODE     # lift a step checkpoint (then run again)
#   scripts/factory/run_muse_v4_graph.sh status
#   TASK=muse-2bit-rehearsal-r1 FACTORY_HOME=~/muse-demo/rehearsal-r1 SESSION=reh ...   # the rehearsal
#
# The working agent and the scheduler agent are JiuwenSwarm agents with Codex as the model: gpt-6.2-sol for
# the worker and the reviewer (MODEL=...), gpt-6.2-astra for the scheduler (SCHEDULER_MODEL=...).
# Everything that executes runs through factory.capped_runner as jobq jobs (cap + machine gate). The controller
# pauses on a halt (HALT.md), a step checkpoint (STEP.md) or a node the scheduler could not finalize.
set -euo pipefail
REPO=${REPO:-$(cd "$(dirname "$0")/../.." && pwd)}
PY=${PY:-$HOME/predemo-spark/jiuwenswarm/.venv/bin/python}
TASK=${TASK:?set TASK (the task id, e.g. muse-2bit-ttft-v4 or muse-2bit-rehearsal-r1)}
export FACTORY_HOME=${FACTORY_HOME:?set FACTORY_HOME (e.g. ~/muse-demo/graph-v4)}
SESSION=${SESSION:?set SESSION (tmux prefix, e.g. muse or reh)}
if [[ "$TASK" == muse-2bit-demo-r8 ]]; then
  # The fast B/P lab consumes the delivered package once, after the graph finishes.
  export FACTORY_LAB_ROUTE=mailbox FACTORY_LAB_MAILBOX="$FACTORY_HOME/lab-mailbox"
  export FACTORY_CAPPED_REPLAY_REGISTRY="${FACTORY_CAPPED_REPLAY_REGISTRY:-$HOME/muse-demo/replay-r8/registry.json}"
  if [[ "$SESSION" != r8 || ( "${1:-}" == run || "${1:-}" == _run ) && "${STEP:-0}" != 1 ]]; then
    echo "The fresh Muse demo requires SESSION=r8 and STEP=1 for execution." >&2
    exit 1
  fi
fi
export FACTORY_REPO=$REPO
export PYTHONPATH=$REPO
export PATH=$HOME/.local/bin:/usr/local/cuda/bin:$PATH
export FACTORY_MODELS=${FACTORY_MODELS:-$HOME/models}
export FACTORY_MUSE_DEMO=${FACTORY_MUSE_DEMO:-$HOME/muse-demo}
export FACTORY_MUSE_SPIKES=${FACTORY_MUSE_SPIKES:-$HOME}
export FACTORY_MUSE_CAPS=${FACTORY_MUSE_CAPS:-/tmp/cc-muse-caps}
export FACTORY_LLAMA_SOURCE=${FACTORY_LLAMA_SOURCE:-$HOME/predemo-spark/llama.cpp-stock}
export FACTORY_LAB_STATE=$FACTORY_HOME/lab-state
export JOBQ_DIR=$FACTORY_LAB_STATE/jobq  # one queue for the worker, the controller and the agent's tools
export FACTORY_HOST_PYTHON=$PY
CODEX=${CODEX:-$HOME/.local/bin/codex}  # Codex 0.171 knows gpt-6.2-sol; the bundled 0.163 does not
export JIUWENSWARM_CODEX_BIN=$CODEX FACTORY_SCHEDULER_CODEX_BIN=$CODEX
# The worker and the reviewer run gpt-6.2-sol (MODEL overrides both); the scheduler runs gpt-6.2-astra
# (SCHEDULER_MODEL overrides it; MODEL does not touch it).
export JIUWENSWARM_CODEX_MODEL=${MODEL:-gpt-6.2-sol} FACTORY_SCHEDULER_MODEL=${SCHEDULER_MODEL:-gpt-6.2-astra}
export FACTORY_REVIEW_MODEL=${MODEL:-gpt-6.2-sol}
export FACTORY_MACHINE_STATE=$FACTORY_HOME/machine.json
export FACTORY_MEMORY_CAP_POLICY='Every model load runs through factory.capped_runner under systemd-run --user --scope -p MemoryMax=96G -p MemorySwapMax=0, and starts only when the machine gate passes (100 GiB available, no GPU process of another user).'
[ "${STEP:-0}" = 1 ] && export FACTORY_STEP=1
GRANTS=(--grant process.exec --grant workspace.read --grant workspace.write)
JOBQ="$REPO/jiuwenswarm/factory/labkit/bin/jobq"

snapshot() {  # what the scheduler agent sees as the machine state
  "$PY" - "$FACTORY_MACHINE_STATE" <<'EOF'
import json, os, shutil, subprocess, sys, time
mem = {}
for line in open('/proc/meminfo'):
    key, value = line.split(':')
    if key in ('MemTotal', 'MemAvailable', 'SwapFree'):
        mem[key] = int(value.split()[0]) // 1024
disk = shutil.disk_usage(os.path.expanduser('~'))
gpu = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,process_name,used_memory', '--format=csv,noheader'],
                     capture_output=True, text=True).stdout.strip().splitlines()
load = os.getloadavg()
running = []
if subprocess.run(['pgrep', '-f', 'sweep.py'], capture_output=True).returncode == 0:
    running.append('agent-size sweep: another measurement on this box holds a capped llama-server; the machine gate waits for it')
out = dict(at=time.strftime('%Y-%m-%dT%H:%M:%S'), memory_mib=dict(total=mem.get('MemTotal'), available=mem.get('MemAvailable')),
           disk_home_free_gb=round(disk.free / 1e9), cpu=dict(cores=os.cpu_count(), load_1m=round(load[0], 1)),
           gpu_processes=gpu, also_running=running,
           rule='Shared box: model loads only through factory.capped_runner (memory cap and machine gate).')
tmp = sys.argv[1] + '.tmp'
json.dump(out, open(tmp, 'w'), indent=1)
os.replace(tmp, sys.argv[1])
EOF
}

worker() {  # the queue that owns the capped runs; survives controller restarts
  if ! tmux has-session -t "$SESSION-jobq" 2>/dev/null; then
    tmux new-session -d -s "$SESSION-jobq" "TASK=$TASK FACTORY_HOME=$FACTORY_HOME SESSION=$SESSION bash '$(readlink -f "$0")' _worker"
    echo "jobq worker in tmux $SESSION-jobq"
  fi
}

case "${1:-}" in
setup)
  mkdir -p "$FACTORY_HOME/agent-workspace/work" "$FACTORY_HOME/work/wiring" "$FACTORY_HOME/packs" \
           "$FACTORY_HOME/agent-data/subscription/codex-home" "$FACTORY_LAB_STATE"
  cp --update=none "$HOME/.codex/auth.json" "$FACTORY_HOME/agent-data/subscription/codex-home/auth.json"
  chmod 600 "$FACTORY_HOME/agent-data/subscription/codex-home/auth.json"
  checkout=$FACTORY_HOME/agent-workspace/llama.cpp-muse
  if [ ! -d "$checkout/.git" ]; then
    git clone -q --no-checkout "$FACTORY_LLAMA_SOURCE" "$checkout"
    git -C "$checkout" checkout -q -b muse-2bit-ttft 9048bad8d6e3a0f9f1726e238e451181c7e02613
  fi
  snapshot
  cd "$REPO"
  "$PY" -m jiuwenswarm.factory.cli init jiuwenswarm/factory/tasks/$TASK.json
  "$PY" scripts/factory/import_prior_artifacts.py $TASK
  ;;
run)
  worker
  # The tmux server keeps its own environment: the session calls back into this script, which sets ours.
  tmux new-session -d -s "$SESSION-graph" "TASK=$TASK FACTORY_HOME=$FACTORY_HOME SESSION=$SESSION STEP=${STEP:-0} bash '$(readlink -f "$0")' _run"
  echo "controller in tmux $SESSION-graph (step ${STEP:-0}); log $FACTORY_HOME/controller.log"
  ;;
_worker)
  exec python3 "$JOBQ" worker >> "$FACTORY_HOME/jobq-worker.log" 2>&1
  ;;
_run)
  rm -f "$FACTORY_HOME/HALT.md" "$FACTORY_HOME/STEP.md"
  snapshot
  (cd "$REPO" && "$PY" scripts/factory/import_prior_artifacts.py --host-reading $TASK)
  (while sleep 60; do snapshot; done) &
  ticker=$!
  trap 'kill "$ticker" 2>/dev/null || true; wait "$ticker" 2>/dev/null || true' EXIT
  cd "$REPO"
  echo "=== run $(date -Is) step ${FACTORY_STEP:-0}" >> "$FACTORY_HOME/controller.log"
  "$PY" scripts/factory/muse_v3_controller.py $TASK "${GRANTS[@]}" 2>&1 | tee -a "$FACTORY_HOME/controller.log"
  ;;
release)
  cd "$REPO"
  "$PY" -m jiuwenswarm.factory.cli release $TASK "$2" "${3:-step checkpoint passed}"
  ;;
snapshot)
  snapshot
  ;;
status)
  cd "$REPO"
  "$PY" -m jiuwenswarm.factory.cli status $TASK --plain || true
  for f in HALT.md STEP.md; do [ -f "$FACTORY_HOME/$f" ] && { echo "--- $f"; cat "$FACTORY_HOME/$f"; }; done
  python3 "$JOBQ" list 2>/dev/null | tail -5 || true
  ;;
*)
  echo "usage: $0 setup|run|release NODE|status|snapshot" >&2; exit 2 ;;
esac
