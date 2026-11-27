#!/usr/bin/env bash
# Native Muse revision 9 operator entry point. Existing graph homes are outside this command's scope.
set -euo pipefail
umask 077

REPO=$(cd "$(dirname "$0")/../.." && pwd)
LAUNCHER=$REPO/scripts/factory/run_muse_r9_graph.sh
FACTORY_MUSE_DEMO=$(realpath "${FACTORY_MUSE_DEMO:-$HOME/muse-demo}")
FACTORY_HOME=$(realpath -m "${FACTORY_HOME:-$FACTORY_MUSE_DEMO/r9/graph}")
if [[ "$FACTORY_HOME/" != "$FACTORY_MUSE_DEMO/r9/"* || "$FACTORY_HOME" == "$FACTORY_MUSE_DEMO/r9" ]]; then
  echo 'FACTORY_HOME must be an isolated directory under the Muse r9 work area.' >&2
  exit 2
fi
PY=${PY:-$HOME/predemo-spark/jiuwenswarm/.venv/bin/python}
SESSION=${SESSION:-r9}
TASK=muse-2bit-demo-r9
TASK_FILE=$REPO/jiuwenswarm/factory/tasks/$TASK.json
JOBQ=$REPO/jiuwenswarm/factory/labkit/bin/jobq

export FACTORY_HOME FACTORY_MUSE_DEMO FACTORY_REPO=$REPO PYTHONPATH=$REPO
export PATH="$HOME/.local/bin:/usr/local/cuda/bin:$PATH"
export FACTORY_HOST_PYTHON=$PY
export FACTORY_LAB_STATE="$FACTORY_HOME/lab-state" JOBQ_DIR="$FACTORY_HOME/lab-state/jobq"
export FACTORY_LAB_ROUTE=mailbox FACTORY_LAB_MAILBOX="$FACTORY_HOME/lab-mailbox"
export FACTORY_MACHINE_STATE="$FACTORY_HOME/machine.json"
export FACTORY_MEMORY_CAP_POLICY='One operator-released measure_engine job under MemoryMax=96G and MemorySwapMax=0 after the Spark machine gate.'
export JIUWENSWARM_CODEX_BIN=${CODEX:-$HOME/.local/bin/codex}
export FACTORY_SCHEDULER_CODEX_BIN=$JIUWENSWARM_CODEX_BIN
export JIUWENSWARM_CODEX_MODEL=${MODEL:-gpt-6.2-sol}
export FACTORY_REVIEW_MODEL=$JIUWENSWARM_CODEX_MODEL
export FACTORY_SCHEDULER_MODEL=${SCHEDULER_MODEL:-gpt-6.2-astra}

snapshot() {
  "$PY" - "$FACTORY_MACHINE_STATE" <<'PY'
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from jiuwenswarm.factory.contract import atomic_json

mem = {}
for line in Path('/proc/meminfo').read_text().splitlines():
    key, _, value = line.partition(':')
    if key in {'MemTotal', 'MemAvailable'}:
        mem[key] = int(value.split()[0]) // 1024
query = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,process_name,used_memory', '--format=csv,noheader'],
                       capture_output=True, text=True, check=False, timeout=15)
atomic_json(sys.argv[1], dict(at=time.strftime('%Y-%m-%dT%H:%M:%S%z'),
    memory_mib=dict(total=mem.get('MemTotal'), available=mem.get('MemAvailable')),
    disk_home_free_gb=round(shutil.disk_usage(Path.home()).free / 1e9),
    cpu=dict(cores=os.cpu_count(), load_1m=round(os.getloadavg()[0], 1)),
    gpu_processes=query.stdout.strip().splitlines() if query.returncode == 0 else None,
    rule='One operator-released measure_engine load through the native capped runner.'))
PY
}

initialized() {
  if [[ ! -f "$FACTORY_HOME/factory.sqlite" || ! -f "$FACTORY_HOME/r9-reference.json" ]]; then
    echo 'Run setup on the isolated revision 9 graph first.' >&2
    exit 2
  fi
}

start_tmux() {
  tmux new-session -d -s "$1" -e "FACTORY_HOME=$FACTORY_HOME"     -e "FACTORY_MUSE_DEMO=$FACTORY_MUSE_DEMO" -e "PY=$PY" -e "SESSION=$SESSION"     -e "CODEX=$JIUWENSWARM_CODEX_BIN" -e "MODEL=$JIUWENSWARM_CODEX_MODEL"     -e "SCHEDULER_MODEL=$FACTORY_SCHEDULER_MODEL" "$LAUNCHER" "$2"
}

cd "$REPO"
case "${1:-}" in
  setup)
    mkdir -p "$FACTORY_HOME"
    if [[ -n "$(find "$FACTORY_HOME" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
      echo 'Setup requires an empty revision 9 graph home.' >&2
      exit 2
    fi
    chmod 700 "$FACTORY_HOME"
    mkdir -p "$FACTORY_HOME/agent-workspace/work" "$FACTORY_LAB_STATE" \
      "$FACTORY_HOME/agent-data/subscription/codex-home"
    install -m 600 "$HOME/.codex/auth.json" "$FACTORY_HOME/agent-data/subscription/codex-home/auth.json"
    ln -s "$(realpath "$FACTORY_MUSE_DEMO/graph-v4/packs")" "$FACTORY_HOME/packs"
    "$PY" - "$TASK_FILE" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import sys

from jiuwenswarm.factory.config import expand_sources
from jiuwenswarm.factory.contract import atomic_json, load
from jiuwenswarm.factory.node_contract import from_contract

task = expand_sources(json.loads(Path(sys.argv[1]).read_text()))
contract = load(task['contract_id'])
if hashlib.sha256(contract.path.read_bytes()).hexdigest() != task['constraints']['contract_sha256']:
    raise SystemExit('The checked-in revision 9 contract differs from its task pin.')
pins = from_contract(contract)['nodes'][0]['verifiers'][0]['inputs']['spec']
reference = task['resources']['r9_reference']
for pin in [*expand_sources(pins).values(), *(value for value in reference.values() if isinstance(value, dict))]:
    path = Path(pin['path'])
    if hashlib.sha256(path.read_bytes()).hexdigest() != pin['sha256']:
        raise SystemExit(f'Run 2 input changed: {path}')
atomic_json(Path(os.environ['FACTORY_HOME']) / 'r9-reference.json', reference)
PY
    snapshot
    "$PY" -m jiuwenswarm.factory.cli init "$TASK_FILE"
    "$PY" scripts/factory/import_prior_artifacts.py "$TASK"
    ;;
  run)
    initialized
    if ! tmux has-session -t "=$SESSION-jobq" 2>/dev/null; then
      start_tmux "$SESSION-jobq" _worker
    fi
    start_tmux "$SESSION-graph" _run
    printf 'Controller in %s-graph. Log at %s/controller.log\n' "$SESSION" "$FACTORY_HOME"
    ;;
  _worker)
    initialized
    exec "$PY" "$JOBQ" worker >> "$FACTORY_HOME/jobq-worker.log" 2>&1
    ;;
  _run)
    initialized
    snapshot
    "$PY" scripts/factory/import_prior_artifacts.py --host-reading "$TASK" >> "$FACTORY_HOME/controller.log"
    printf '=== Run %s ===\n' "$(date -Is)" >> "$FACTORY_HOME/controller.log"
    exec "$PY" -m jiuwenswarm.factory.cli run "$TASK" --grant process.exec >> "$FACTORY_HOME/controller.log" 2>&1
    ;;
  release)
    initialized
    "$PY" -m jiuwenswarm.factory.cli release "$TASK" "${2:?supply the node ID}" "${3:?supply the release reason}"
    ;;
  status)
    initialized
    "$PY" -m jiuwenswarm.factory.cli status "$TASK" --plain
    ;;
  *)
    printf 'Usage: %s setup|run|release NODE REASON|status\n' "$0" >&2
    exit 2
    ;;
esac
