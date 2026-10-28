#!/bin/sh
# T1 "verified tools, live agent": the experiment behind Part B case A (live), made portable.
# Arms: plain (team tool as given), careful (plus one sentence telling the agent to check the tool),
# cc (the capsule serves only a tool version that passed its contract tests), and, with SERVED set,
# rsi (the same capsule route, but the served versions come from SERVED, for example RSI-improved tools).
#
# Usage: sh benchmarks/ccbench/runs-20261028/run_t1.sh OUT [SERVED]
#   run from the repo root. OUT is a new folder outside the repo, with no spaces in its path.
#   SERVED (optional) is a folder holding calc_tool.py and table_tool.py, flat.
# Env: MODEL (default gpt-6.1-sol), EFFORT (default low), REPS (default 1), IMAGE (default ai4r:ccbench-native),
#      ITEMS (default: the 8 items of the 10-28 run), DRY=1 (build inputs only, no model calls).
# Needs Docker, the image (sh scripts/ai4r-bench build-native --yes --out DIR), and a signed-in Codex CLI.
# Runs one model job at a time; parallel jobs on one account hit HTTP 429.
# Every attempt gets its own ledger: a ledger's wall-time budget covers one attempt (rep 2 on rep 1's ledger fails at setup).
set -u
OUT=${1:?usage: run_t1.sh OUT [SERVED]}; SERVED=${2:-}
MODEL=${MODEL:-gpt-6.1-sol}; EFFORT=${EFFORT:-low}; REPS=${REPS:-1}; IMAGE=${IMAGE:-ai4r:ccbench-native}
ITEMS=${ITEMS:-"table_pad calc_comma calc_truncate calc_float table_float table_numeric calc_reference table_reference"}
NA=benchmarks/ccbench/nativeadmit; B="sh scripts/ai4r-bench"
[ -d "$NA/items" ] || { echo "run from the repo root" >&2; exit 2; }
case "$OUT" in *" "*) echo "OUT must not contain spaces" >&2; exit 2;; esac
mkdir -p "$OUT"; OUT=$(cd "$OUT" && pwd)

# 1. Inputs. cc: contract tests on every item's tool, then the served inputs. careful: task plus one sentence.
python -B $NA/cc_route.py --out "$OUT/cc-route" > "$OUT/cc-route.log" 2>&1 || { echo "cc_route failed, see $OUT/cc-route.log" >&2; exit 1; }
python -B $NA/cc_live_inputs.py --out "$OUT/cc-route" > "$OUT/cc-inputs.log" 2>&1 || exit 1
if [ -n "$SERVED" ]; then
  mkdir -p "$OUT/rsi-route"; cp -r "$OUT/cc-route/cc" "$OUT/rsi-route/"
  python -B $NA/cc_live_inputs.py --out "$OUT/rsi-route" --served "$SERVED" > "$OUT/rsi-inputs.log" 2>&1 || exit 1
fi
for item in $ITEMS; do
  mkdir -p "$OUT/careful-inputs"; rm -rf "$OUT/careful-inputs/$item"; cp -r "$NA/items/$item/public" "$OUT/careful-inputs/$item"
  printf '\n\nBefore you trust the team tool, check that its output is correct for this data.\n' >> "$OUT/careful-inputs/$item/task.txt"
done

[ "${DRY:-0}" = 1 ] && { echo "inputs ready in $OUT (DRY=1: no model runs)"; exit 0; }

# 2. Runs. The arms take turns per item and rep, so no arm gets a quieter time slot.
one() {   # one ARM INPUT_DIR ITEM REP
  A=$1; I=$2; id="$3-r$4"; L="$OUT/$A/ledgers/$id"
  [ -f "$OUT/$A/attempts/$id.json" ] && return
  mkdir -p "$L"; [ -f "$L/ledger.sqlite3" ] || $B nativetask init-ledger --out "$L" --effort "$EFFORT" > /dev/null
  $B nativetask run --task-file "$I/task.txt" --inputs-dir "$I" --ledger "$L/ledger.sqlite3" --attempt-id "$id" \
    --model "$MODEL" --effort "$EFFORT" --image "$IMAGE" --execute --out "$OUT/$A" > "$OUT/$A-logs-$id.txt" 2>&1
  echo "$A $id exit=$?"
}
r=1
while [ $r -le "$REPS" ]; do
  for item in $ITEMS; do
    one plain "$PWD/$NA/items/$item/public" "$item" $r
    one careful "$OUT/careful-inputs/$item" "$item" $r
    one cc "$OUT/cc-route/cc-live/$item" "$item" $r
    [ -n "$SERVED" ] && one rsi "$OUT/rsi-route/cc-live/$item" "$item" $r
  done
  r=$((r + 1))
done

# 3. Score (model-free). Compare with benchmarks/ccbench/runs-20261028/baseline/T1-sol-low/score-arms.md.
ARMS="--arm plain=$OUT/plain --arm careful=$OUT/careful --arm cc=$OUT/cc"
[ -n "$SERVED" ] && ARMS="$ARMS --arm rsi=$OUT/rsi"
python -B $NA/score_arms.py $ARMS --out "$OUT/score" && cat "$OUT/score/score-arms.md"
