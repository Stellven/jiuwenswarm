#!/bin/bash
# Recorded run of the Muse demo graph (contract muse-q2-ttft-v3, preliminary node contracts) on the Spark.
#
#   scripts/factory/run_muse_v3_graph.sh setup     # factory home, owned checkout, task init (once)
#   scripts/factory/run_muse_v3_graph.sh run       # controller in tmux session muse-graph (resume = run again)
#   scripts/factory/run_muse_v3_graph.sh status
#
# The working agent and the scheduler agent are JiuwenSwarm agents with Codex (gpt-6.2-sol) as the model.
# No model is loaded: the task reuses the packs, smoke runs, accuracy run and lab logs listed in its
# resources.prior_artifacts and runs their verifiers on them.
set -euo pipefail
REPO=${REPO:-$(cd "$(dirname "$0")/../.." && pwd)}
PY=${PY:-$HOME/predemo-spark/jiuwenswarm/.venv/bin/python}
export FACTORY_HOME=${FACTORY_HOME:-$HOME/muse-demo/graph-v3}
export PYTHONPATH=$REPO
export PATH=$HOME/.local/bin:/usr/local/cuda/bin:$PATH
export FACTORY_MODELS=${FACTORY_MODELS:-$HOME/models}
export FACTORY_MUSE_DEMO=${FACTORY_MUSE_DEMO:-$HOME/muse-demo}
export FACTORY_MUSE_SPIKES=${FACTORY_MUSE_SPIKES:-$HOME}
export FACTORY_MUSE_CAPS=${FACTORY_MUSE_CAPS:-/tmp/cc-muse-caps}
export FACTORY_LLAMA_SOURCE=${FACTORY_LLAMA_SOURCE:-$HOME/predemo-spark/llama.cpp-stock}
# Codex 0.171 knows gpt-6.2-sol; the bundled 0.163 does not.
CODEX=${CODEX:-$HOME/.local/bin/codex}
export JIUWENSWARM_CODEX_BIN=$CODEX FACTORY_SCHEDULER_CODEX_BIN=$CODEX
export JIUWENSWARM_CODEX_MODEL=${MODEL:-gpt-6.2-sol} FACTORY_SCHEDULER_MODEL=${MODEL:-gpt-6.2-sol}
export FACTORY_REVIEW_MODEL=${MODEL:-gpt-6.2-sol}
export FACTORY_MACHINE_STATE=$FACTORY_HOME/machine.json
TASK=muse-q2-ttft-v3
GRANTS=(--grant process.exec --grant workspace.read --grant workspace.write)

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
    running.append('agent-size sweep: another measurement on this box holds a capped llama-server; leave it alone')
out = dict(at=time.strftime('%Y-%m-%dT%H:%M:%S'), memory_mib=dict(total=mem.get('MemTotal'), available=mem.get('MemAvailable')),
           disk_home_free_gb=round(disk.free / 1e9), cpu=dict(cores=os.cpu_count(), load_1m=round(load[0], 1)),
           gpu_processes=gpu, also_running=running,
           rule='Shared box: no model loads in this run; compile with at most 4 jobs.')
tmp = sys.argv[1] + '.tmp'
json.dump(out, open(tmp, 'w'), indent=1)
os.replace(tmp, sys.argv[1])
EOF
}

case "${1:-}" in
setup)
  mkdir -p "$FACTORY_HOME/agent-workspace" "$FACTORY_HOME/agent-data/subscription/codex-home"
  cp -n "$HOME/.codex/auth.json" "$FACTORY_HOME/agent-data/subscription/codex-home/auth.json"
  chmod 600 "$FACTORY_HOME/agent-data/subscription/codex-home/auth.json"
  checkout=$FACTORY_HOME/agent-workspace/llama.cpp-muse
  if [ ! -d "$checkout/.git" ]; then
    git clone -q --no-checkout "$FACTORY_LLAMA_SOURCE" "$checkout"
    git -C "$checkout" checkout -q -b muse-q2-ttft 9048bad8d6e3a0f9f1726e238e451181c7e02613
  fi
  snapshot
  cd "$REPO"
  "$PY" -m jiuwenswarm.factory.cli init jiuwenswarm/factory/tasks/muse-q2-ttft-v3.json
  ;;
run)
  # The tmux server keeps its own environment: the session calls back into this script, which sets ours.
  tmux new-session -d -s muse-graph "bash '$(readlink -f "$0")' _run"
  echo "controller in tmux muse-graph; log $FACTORY_HOME/controller.log"
  ;;
_run)
  snapshot
  (while sleep 60; do snapshot; done) &
  ticker=$!
  cd "$REPO"
  "$PY" scripts/factory/muse_v3_controller.py $TASK "${GRANTS[@]}" 2>&1 | tee -a "$FACTORY_HOME/controller.log" || true
  kill $ticker
  ;;
snapshot)
  snapshot
  ;;
status)
  cd "$REPO"
  "$PY" -m jiuwenswarm.factory.cli status $TASK --plain || true
  "$PY" - <<'EOF'
import os
from jiuwenswarm.factory.store import Store
from jiuwenswarm.factory import scheduler
store = Store(os.environ['FACTORY_HOME'])
work = scheduler.next_work(store, 'muse-q2-ttft-v3')
print('runnable', [i['node_id'] for i in work['runnable']], 'to_finalize', [i['node_id'] for i in work.get('to_finalize', [])])
for row in store._db.execute("SELECT kind, \"values\" FROM observations WHERE task_id=? AND kind LIKE 'node_contract_%' ORDER BY created", ('muse-q2-ttft-v3',)):
    import json
    v = json.loads(row[1])
    print(row[0], v['node_id'], v.get('by'), 'bound', (v.get('final') or {}).get('work', {}).get('bound_ccs'), v.get('problems', '')[:2] if v.get('problems') else '')
EOF
  ;;
*)
  echo "usage: $0 setup|run|status|snapshot" >&2; exit 2 ;;
esac
