#!/bin/sh
# Bench B (trapcheck) native arm rerun: 11 fixtures x 1 rep on ai4r:ccbench-native, model gpt-6.1-sol via codex.
# Usage: AI4R_CODEX_BIN=... sh collect.sh <repo> <out>
#   <repo>  product repo (jiuwenswarm-agentic checkout)
#   <out>   output dir: attempts/, sessions/<fixture>-r1/, ledgers/<fixture>/, logs-<fixture>-r1.txt
# Fixtures are read from the folder next to this script: fixtures/<name>/{task.txt,inputs/}.
# OLD_MODELS=1 uses the model each fixture had on 10-26 (gpt-6-luna for clean-cb8afcdb, conflicts-e6830418,
# overreach-1fdc5eaf); default is gpt-6.1-sol for all 11.
# One ledger per fixture (a ledger holds 256 calls; each run is capped at 80). An attempt whose record exists is skipped.
# To redo a failed attempt, delete attempts/<id>.json and sessions/<id> first.
set -u
REPO=$1; OUT=$2
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$OUT"; OUT=$(cd "$OUT" && pwd)
cd "$REPO" || exit 2
B="sh scripts/ai4r-bench"
for d in "$HERE"/fixtures/*/; do
  fx=$(basename "$d")
  M=${MODEL:-gpt-6.1-sol}   # MODEL=gpt-6-luna for the weaker-model run
  if [ "${OLD_MODELS:-0}" = 1 ]; then
    case $fx in clean-cb8afcdb|conflicts-e6830418|overreach-1fdc5eaf) M=gpt-6-luna;; esac
  fi
  L="$OUT/ledgers/$fx"
  [ -f "$L/ledger.sqlite3" ] || { mkdir -p "$L"; $B nativetask init-ledger --out "$L" > /dev/null; }
  id="$fx-r1"
  [ -f "$OUT/attempts/$id.json" ] && continue
  $B nativetask run --task-file "$d/task.txt" --inputs-dir "$d/inputs" --ledger "$L/ledger.sqlite3" --attempt-id "$id" \
    --model "$M" --image ai4r:ccbench-native --execute --out "$OUT" > "$OUT/logs-$id.txt" 2>&1
  echo "$id model=$M exit=$?"
done
