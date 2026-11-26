#!/bin/bash
# Rehearse scheduler proposals against an isolated copy of a quiescent, freshly initialized graph.
set -euo pipefail
REPO=$(cd "$(dirname "$0")/../.." && pwd)
SRC=${SRC:?set SRC to the initialized factory home}
DRY=${DRY:?set DRY to a new scratch directory}
TASK=${TASK:?set TASK to the fresh demo task}
PY=${PY:-$HOME/predemo-spark/jiuwenswarm/.venv/bin/python}
if [[ -e "$DRY" || -L "$DRY" || "$(realpath -m "$DRY")/" == "$(realpath "$SRC")/"* ]]; then
  echo 'DRY must be a new directory outside SRC' >&2
  exit 1
fi
mkdir -m 700 "$DRY"
rsync -a --exclude=/packs --exclude=/controller.lock "$SRC/" "$DRY/"
ln -s "$(realpath "$SRC/packs")" "$DRY/packs"
export FACTORY_HOME="$DRY" FACTORY_REPO="$REPO" PYTHONPATH="$REPO"
export FACTORY_MACHINE_STATE="$DRY/machine.json" JOBQ_DIR="$DRY/lab-state/jobq"
export FACTORY_SCHEDULER_CODEX_BIN="${CODEX:-$HOME/.local/bin/codex}" FACTORY_SCHEDULER_MODEL=gpt-6.2-astra
cd "$REPO"
"$PY" scripts/factory/rehearse_scheduler.py "$TASK" "$@"
