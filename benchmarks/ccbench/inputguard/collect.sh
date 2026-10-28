#!/bin/sh
# T2 (inputguard): 11 fixtures x 1 rep x 3 arms, serial, one model job at a time.
# Usage: [MODEL=gpt-6-luna] [ARMS="plain careful cc"] (an extra arm: ARMS="rsi=cc" CODE_ROOT=/path/to/rsi/checkout) [FIXTURES="a b"] AI4R_CODEX_BIN=... sh collect.sh <repo> <out>
#   <repo>  product repo (jiuwenswarm-agentic checkout, run from here so scripts/ai4r-bench resolves)
#   <out>   run folder. Layout: inputs/<arm>/<fixture>/ (from prepare.py), <arm>/{attempts,sessions,ledgers}/ per arm.
# Needs: prepare.py already run into <out>, Docker, the image ai4r:ccbench-native, a signed-in codex.
# Resumable: an attempt whose record <out>/<arm>/attempts/<fixture>-r1.json exists is skipped (finished, or a CC guard halt).
# To redo one, delete that record and <out>/<arm>/sessions/<fixture>-r1 first. One ledger per fixture and arm.
# CC arm: run_guard.py runs the product input guard first; on a halt it writes the CC session and no agent runs.
# RSI/other code under test for the guard: set AI4R_CODE_ROOT (or CODE_ROOT=...) to that checkout.
set -u
REPO=$1; OUT=$2
HERE=$(cd "$(dirname "$0")" && pwd)
MODEL=${MODEL:-gpt-6-luna}
ARMS=${ARMS:-plain careful cc}
mkdir -p "$OUT"; OUT=$(cd "$OUT" && pwd)
[ -d "$OUT/inputs" ] || { echo "collect: $OUT/inputs missing; run: python -B $HERE/prepare.py --out $OUT" >&2; exit 2; }
cd "$REPO" || exit 2
B="sh scripts/ai4r-bench"
PY=${AI4R_PYTHON:-python}
FX_ALL=$(ls "$OUT/inputs/plain")
for spec in $ARMS; do
  arm=${spec%%=*}; base=${spec#*=}; [ "$base" = "$spec" ] && base=$arm     # NAME=BASE: a new arm that runs as BASE (plain, careful or cc)
  A="$OUT/$arm"; mkdir -p "$A"
  for fx in ${FIXTURES:-$FX_ALL}; do
    id="$fx-r1"
    [ -f "$A/attempts/$id.json" ] && continue
    if [ "$base" = cc ]; then
      if [ -n "${CODE_ROOT:-}" ]; then
        $PY -B "$HERE/run_guard.py" --inputs "$OUT/inputs/$base" --out "$A" --only "$fx" --code-root "$CODE_ROOT"
      else
        $PY -B "$HERE/run_guard.py" --inputs "$OUT/inputs/$base" --out "$A" --only "$fx"
      fi
      [ -f "$A/attempts/$id.json" ] && continue      # the guard halted: no agent
    fi
    d="$OUT/inputs/$base/$fx"
    L="$A/ledgers/$fx"
    [ -f "$L/ledger.sqlite3" ] || { mkdir -p "$L"; $B nativetask init-ledger --out "$L" > /dev/null; }
    $B nativetask run --task-file "$d/task.txt" --inputs-dir "$d/inputs" --ledger "$L/ledger.sqlite3" --attempt-id "$id" \
      --model "$MODEL" --image ai4r:ccbench-native --execute --out "$A" > "$A/logs-$id.txt" 2>&1
    echo "$arm $id model=$MODEL exit=$?"
  done
done
