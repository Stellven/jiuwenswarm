#!/bin/bash
# Scheduler dry run for contract rev 8 (no GPU, no worker): copy the live factory home (packs linked, not copied),
# apply the contract revision there, and let the scheduler agent finalize the nodes still to run, one by one.
# The live run is not touched. Read the briefs and finals afterwards:
#
#   scripts/factory/scheduler_dry_run_v4.sh [NODE ...]       # default: size_prefill_batch build_image deliver_to_lab
#   DRY=/tmp/sched-dry-v4 (scratch home), SRC=~/muse-demo/graph-v4, TASK=muse-2bit-ttft-v4
set -euo pipefail
REPO=${REPO:-$(cd "$(dirname "$0")/../.." && pwd)}
PY=${PY:-$HOME/predemo-spark/jiuwenswarm/.venv/bin/python}
SRC=${SRC:-$HOME/muse-demo/graph-v4}
DRY=${DRY:-/tmp/sched-dry-v4}
TASK=${TASK:-muse-2bit-ttft-v4}
NODES=("$@"); [ ${#NODES[@]} -gt 0 ] || NODES=(size_prefill_batch build_image deliver_to_lab)
if pgrep -u "$USER" -f "factory.controller.*$SRC" >/dev/null; then echo "the live controller runs; stop it first" >&2; exit 1; fi
rm -rf "$DRY"; mkdir -p "$DRY"
rsync -a --exclude packs --exclude controller.lock "$SRC/" "$DRY/"
ln -s "$SRC/packs" "$DRY/packs"
export FACTORY_HOME=$DRY PYTHONPATH=$REPO FACTORY_REPO=$REPO FACTORY_LAB_STATE=$DRY/lab-state JOBQ_DIR=$DRY/lab-state/jobq
export FACTORY_MACHINE_STATE=$DRY/machine.json PATH=$HOME/.local/bin:$PATH
CODEX=${CODEX:-$HOME/.local/bin/codex}
export JIUWENSWARM_CODEX_BIN=$CODEX FACTORY_SCHEDULER_CODEX_BIN=$CODEX
export FACTORY_SCHEDULER_MODEL=${SCHEDULER_MODEL:-gpt-6.2-astra}
OUT=$DRY/dry-run; mkdir -p "$OUT"
"$PY" -m jiuwenswarm.factory.cli revise "$TASK" "dry run of contract revision 8" --dry-run | tee "$OUT/revise-plan.txt"
"$PY" -m jiuwenswarm.factory.cli revise "$TASK" "dry run of contract revision 8" | tee "$OUT/revise.txt"
for node in "${NODES[@]}"; do
  echo "== $node"
  "$PY" - "$TASK" "$node" > "$OUT/$node.brief.json" <<'EOF'
import json, sys
from jiuwenswarm.factory.store import Store
from jiuwenswarm.factory.scheduler import finalize_brief
import os
store = Store(os.environ['FACTORY_HOME'])
print(json.dumps(finalize_brief(store, sys.argv[1], sys.argv[2]), indent=1, default=str))
EOF
  echo "brief $(wc -c < "$OUT/$node.brief.json") bytes"
  start=$(date +%s)
  "$PY" -m jiuwenswarm.factory.scheduler_agent --home "$DRY" --task "$TASK" --node "$node" > "$OUT/$node.agent.log" 2>&1 \
    && echo "scheduler done in $(( $(date +%s) - start )) s" || echo "scheduler FAILED ($?), see $OUT/$node.agent.log"
done
"$PY" - "$TASK" > "$OUT/finals.json" <<'EOF'
import json, os, sys
from jiuwenswarm.factory.store import Store
from jiuwenswarm.factory.scheduler import recorded_finals
store = Store(os.environ['FACTORY_HOME'])
host = getattr(store, '_store', store)
rows = host._db.execute('SELECT "values" FROM observations WHERE task_id=? AND kind LIKE ? ORDER BY created, rowid',
                        (sys.argv[1], '%refus%')).fetchall()
print(json.dumps(dict(finals=recorded_finals(host, sys.argv[1])[-6:], refusals=[json.loads(r[0]) for r in rows][-10:]),
                 indent=1, default=str))
EOF
echo "outputs in $OUT"
