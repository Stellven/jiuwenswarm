#!/bin/sh
# Bench A collection: native arm 12 items x 3 reps on ai4r:ccbench-native; CC arm is deterministic (1 route per item).
# Usage: AI4R_CODEX_BIN=... sh collect.sh <repo> <out>
set -u
REPO=$1; OUT=$2; cd "$REPO"
B="sh scripts/ai4r-bench"
for d in benchmarks/ccbench/nativeadmit/items/*/; do
  item=$(basename "$d"); I="$REPO/$d/public"
  L="$OUT/ledgers/$item"   # one ledger per item: 3 runs x 30-call cap stays under the 256-call ledger limit
  [ -f "$L/ledger.sqlite3" ] || { mkdir -p "$L"; $B nativetask init-ledger --out "$L" > /dev/null; }
  for r in 1 2 3; do
    id="$item-r$r"
    [ -f "$OUT/attempts/$id.json" ] && continue
    $B nativetask run --task-file "$I/task.txt" --inputs-dir "$I" --ledger "$L/ledger.sqlite3" --attempt-id "$id" \
      --image ai4r:ccbench-native --execute --out "$OUT" > "$OUT/logs-$id.txt" 2>&1
    echo "$id exit=$?"
  done
done
$B nativeadmit cc_route --out "$OUT/cc" > "$OUT/cc-route.log" 2>&1; echo "cc_route exit=$?"
