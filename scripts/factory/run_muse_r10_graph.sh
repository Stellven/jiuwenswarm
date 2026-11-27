#!/usr/bin/env bash
# Native Muse revision 10 operator entry point. Existing graph homes are outside this command's scope.
set -euo pipefail
umask 077

REPO=$(cd "$(dirname "$0")/../.." && pwd)
LAUNCHER=$REPO/scripts/factory/run_muse_r10_graph.sh
FACTORY_MUSE_DEMO=$(realpath "${FACTORY_MUSE_DEMO:-$HOME/muse-demo}")
FACTORY_HOME=$(realpath -m "${FACTORY_HOME:-$FACTORY_MUSE_DEMO/r10/graph}")
if [[ "$FACTORY_HOME/" != "$FACTORY_MUSE_DEMO/r10/"* || "$FACTORY_HOME" == "$FACTORY_MUSE_DEMO/r10" ]]; then
  echo 'FACTORY_HOME must be an isolated directory under the Muse r10 work area.' >&2
  exit 2
fi
PY=${PY:-$HOME/predemo-spark/jiuwenswarm/.venv/bin/python}
SESSION=${SESSION:-r10}
TASK=muse-2bit-demo-r10
TASK_FILE=$REPO/jiuwenswarm/factory/tasks/$TASK.json
JOBQ=$REPO/jiuwenswarm/factory/labkit/bin/jobq

export FACTORY_HOME FACTORY_MUSE_DEMO FACTORY_REPO=$REPO PYTHONPATH=$REPO
export PATH="$HOME/.local/bin:/usr/local/cuda/bin:$PATH"
export FACTORY_HOST_PYTHON=$PY
export FACTORY_LAB_STATE="$FACTORY_HOME/lab-state" JOBQ_DIR="$FACTORY_HOME/lab-state/jobq"
export FACTORY_LAB_ROUTE=mailbox FACTORY_LAB_MAILBOX="$FACTORY_HOME/lab-mailbox"
export FACTORY_MACHINE_STATE="$FACTORY_HOME/machine.json"
export FACTORY_MEMORY_CAP_POLICY='Factory stage cannot load Muse. After qualified delivery, lab uses up to three operator-gated serial loads under MemoryMax=96G and MemorySwapMax=0.'
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
    rule='No model loads in the factory stage.'))
PY
}

initialized() {
  if [[ ! -f "$FACTORY_HOME/factory.sqlite" ]]; then
    echo 'Run setup on the isolated revision 10 graph first.' >&2
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
      echo 'Setup requires an empty revision 10 graph home.' >&2
      exit 2
    fi
    chmod 700 "$FACTORY_HOME"
    mkdir -p "$FACTORY_HOME/agent-workspace/work" "$FACTORY_LAB_STATE" \
      "$FACTORY_HOME/agent-data/subscription/codex-home"
    install -m 600 "$HOME/.codex/auth.json" "$FACTORY_HOME/agent-data/subscription/codex-home/auth.json"
    "$PY" - "$TASK_FILE" <<'PY'
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from jiuwenswarm.factory.config import expand_sources
from jiuwenswarm.factory.contract import load_for_task
from jiuwenswarm.factory.node_contract import from_contract

task = expand_sources(json.loads(Path(sys.argv[1]).read_text()))
contract = load_for_task(task, task['contract_id'])
protocol = expand_sources(contract['extensions']['muse.r10-dispatch'])
pin = protocol['parent_reference']
path = Path(pin['path'])
if hashlib.sha256(path.read_bytes()).hexdigest() != pin['sha256']:
    raise SystemExit('AQBC parent reference differs from the frozen contract pin.')
parent = json.loads(path.read_bytes())
if any(parent[key] != value for key, value in protocol['baseline'].items()):
    raise SystemExit('AQBC parent identity does not match the frozen contract.')
root = path.parent.parent
for name, evidence in parent['evidence'].items():
    artifact = (root / evidence['path']).resolve(strict=True)
    if not artifact.is_relative_to(root) or hashlib.sha256(artifact.read_bytes()).hexdigest() != evidence['sha256']:
        raise SystemExit(f'Parent evidence changed: {name}')
fixture_diff = Path(task['resources']['operator_inputs']['dispatch_fixture_diff']['path'])
if not fixture_diff.is_file() or not fixture_diff.stat().st_size:
    raise SystemExit('The recorded dispatch fixture instrumentation diff is missing.')
trace = next(node for node in from_contract(contract)['nodes'] if node['node_id'] == 'trace_dispatch')
request = expand_sources(trace['verifiers'][0]['inputs']['request'])
source = parent['engine_source']
tree = subprocess.check_output(['git', '-C', request['source_root'], 'rev-parse',
                                source['commit'] + '^{tree}'], text=True).strip()
if tree != source['tree']:
    raise SystemExit('AQBC source tree differs from the frozen contract pin.')
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
  status)
    initialized
    "$PY" -m jiuwenswarm.factory.cli status "$TASK" --plain
    ;;
  *)
    printf 'Usage: %s setup|run|status\n' "$0" >&2
    exit 2
    ;;
esac
