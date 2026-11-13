#!/usr/bin/env bash
# Record one real, agent-driven factory run in tmux (raw typescript + timing are kept untouched).
#   jiuwenswarm/factory/demo_record.sh [task.json]       # starts the run and the recording
#   scriptreplay -t OUT/session.timing OUT/session.typescript   # replay the raw recording
# Layout: left = factory story (decisions, reasons, builds, screens, A/Bs), right = source diff/images
# and the CC activity feed. The controller's own log goes to OUT/controller.log (not on screen).
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
TASK_JSON=${1:-$ROOT/jiuwenswarm/factory/tasks/demo-incremental.json}
FH=${FACTORY_HOME:-$HOME/.jiuwenswarm-factory}
OUT=$FH/demo-recording/$(date -u +%Y%m%dT%H%M%SZ)
PY=$ROOT/.venv/bin/python
JW=$ROOT/.venv/bin/jiuwenswarm
SESSION=factory-demo
mkdir -p "$OUT"
cd "$ROOT"

# RESUME_TASK=<task id> continues an interrupted task (e.g. after a host reboot) in a new recording segment.
# The shared jobq needs a running worker (nothing starts one; a reboot kills it). Without one, builds sit queued
# until the task's budget is gone. Start it if absent and refuse to run without it.
JOBQ_ROOT=${JOBQ_ROOT:-$HOME/projects/siminfeng}
if ! pgrep -f "bin/jobq worker" > /dev/null; then
  nohup python3 "$JOBQ_ROOT/bin/jobq" worker > "$FH/jobq-worker.log" 2>&1 < /dev/null &
  sleep 3
fi
pgrep -f "bin/jobq worker" > /dev/null || { echo "no jobq worker running (see $FH/jobq-worker.log)"; exit 1; }
T=${RESUME_TASK:-$($JW factory init "$TASK_JSON")}
echo "$T" > "$OUT/task-id"; echo "$T" > "$FH/demo-task-id-3"
cp "$TASK_JSON" "$OUT/task.json"
git rev-parse HEAD > "$OUT/jiuwenswarm-commit"

INTRO="clear; printf '\\033[1m JiuwenSwarm software factory · task %s\\033[0m\\n\\n' ${T:8:8}; \
$PY -c 'import json,sys,textwrap; t=json.load(open(sys.argv[1])); print(chr(10).join(textwrap.wrap(t[\"objective\"],98,initial_indent=\" \",subsequent_indent=\" \")))' $OUT/task.json; \
printf '\\n\\033[90m plain llama.cpp cf34d3113 · contract qwen36-quick-v1 · Jetson Orin Nano 8GB · Qwen3.6-35B-A3B\\033[0m\\n\\n'; sleep 12"

tmux kill-session -t "$SESSION" 2>/dev/null || true
tmux new-session -d -s "$SESSION" -x 172 -y 48 -n run \
  "$INTRO; $PY -m jiuwenswarm.factory.cli story $T --follow --demo; sleep infinity"
tmux set -t "$SESSION" window-size manual; tmux resize-window -t "$SESSION:run" -x 172 -y 48
tmux split-window -h -t "$SESSION:run" -l 70 "$PY -u -m jiuwenswarm.factory.demo_panes source $T"
tmux split-window -v -t "$SESSION:run.1" -l 26 "$PY -u -m jiuwenswarm.factory.demo_panes cc $T"
tmux set -t "$SESSION" status off
tmux set -t "$SESSION" pane-border-style fg=colour240
tmux set -t "$SESSION" pane-active-border-style fg=colour240

# Recording client: a fixed-size pty attached read-only to the session.
nohup script -q -f -T "$OUT/session.timing" \
  -c "stty rows 48 cols 172; tmux attach -r -t $SESSION" "$OUT/session.typescript" \
  > /dev/null 2>&1 < /dev/null &
echo $! > "$OUT/recorder.pid"

# The agent run itself (controller log kept, not shown).
export FACTORY_HOME="$FH" PATH=/usr/local/cuda/bin:$ROOT/.venv/bin:$PATH JIUWENSWARM_CODEX_AGENT_EFFORT=${JIUWENSWARM_CODEX_AGENT_EFFORT:-medium}
nohup "$JW" factory run "$T" --grant process.exec --grant workspace.read --grant workspace.write \
  --grant gpu.use > "$OUT/controller.log" 2>&1 < /dev/null &
echo $! > "$OUT/controller.pid"
echo "task $T"
echo "recording $OUT"
