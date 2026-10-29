#!/bin/sh
# T1 on gpt-6.1-sol at LOW effort (the weaker model; luna does not follow the bridge's tool protocol).
# 8 items (6 subtle broken tools + 2 correct references) x 1 rep x 3 arms = 24 runs. Waits for the luna slate first (one codex job at a time).
set -u
C=/c/Users/m50066326/huawei/AI4Research-Development/ai4r-bench-clean; R=/c/Users/m50066326/huawei/outputs/rebench-20261028
while [ ! -f "$R/slate/SUMMARY.md" ]; do sleep 60; done; echo "slate finished; starting T1 low"
cd "$C"; B="sh scripts/ai4r-bench"; NA=$C/benchmarks/ccbench/nativeadmit/items
ITEMS="table_pad calc_comma calc_truncate calc_float table_float table_numeric calc_reference table_reference"
arm() {
  OUT=$1; IN=$2; mkdir -p "$OUT"
  for item in $ITEMS; do
    L="$OUT/ledgers/$item"
    [ -f "$L/ledger.sqlite3" ] || { mkdir -p "$L"; $B nativetask init-ledger --out "$L" --effort low > /dev/null; }
    I=$IN/$item; [ "$IN" = public ] && I=$NA/$item/public
    id="$item-r1"; [ -f "$OUT/attempts/$id.json" ] && continue
    $B nativetask run --task-file "$I/task.txt" --inputs-dir "$I" --ledger "$L/ledger.sqlite3" --attempt-id "$id" \
      --model gpt-6.1-sol --effort low --image ai4r:ccbench-native --execute --out "$OUT" > "$OUT/logs-$id.txt" 2>&1
    echo "$(basename "$OUT") $id exit=$?"
  done
}
arm "$R/T1low-plain" public
arm "$R/T1low-careful" "$R/A-verify-inputs"
arm "$R/T1low-cc" "$R/A-cc/cc-live"
