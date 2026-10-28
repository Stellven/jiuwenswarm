#!/bin/sh
# Second live queue: broken tools and broken inputs across models, plus the live CC arm for A.
# Runs from the clean worktree, moved to the commit that has cc_live_inputs.py. One job at a time.
# T1 on luna (Muk 10-28: sol saturates): plain, careful and CC arms, 12 items x 2 reps = 24 runs each.
set -u
C=/c/Users/m50066326/huawei/AI4Research-Development/ai4r-bench-clean; R=/c/Users/m50066326/huawei/outputs/rebench-20261028
NA=$C/benchmarks/ccbench/nativeadmit/items
git -C "$C" checkout -q --detach af29f5e4d && git -C "$C" log --oneline -1
cd "$C"; B="sh scripts/ai4r-bench"
python -B benchmarks/ccbench/nativeadmit/cc_live_inputs.py --out "$(cygpath -w $R/A-cc)" > $R/A-cc-live-inputs.log 2>&1; echo "cc-live inputs=$?"
# Fairness control: plain JiuwenSwarm, same files, task plus one sentence telling it to check the tool (no CC).
V=$R/A-verify-inputs; rm -rf "$V"; mkdir -p "$V"
for d in "$NA"/*/; do item=$(basename "$d"); cp -r "$d/public" "$V/$item"
  printf '

Before you trust the team tool, check that its output is correct for this data.
' >> "$V/$item/task.txt"; done
(cd "$V" && find . -type f | sort | xargs sha256sum) > "$R/A-verify-inputs.sha256"
# arm OUT MODEL INPUTS   (INPUTS = public for the plain item files, else a folder holding <item>/)
arm() {
  OUT=$1; M=$2; IN=$3; mkdir -p "$OUT"
  for d in "$NA"/*/; do
    item=$(basename "$d"); L="$OUT/ledgers/$item"
    [ -f "$L/ledger.sqlite3" ] || { mkdir -p "$L"; $B nativetask init-ledger --out "$L" > /dev/null; }
    I=$IN/$item; [ "$IN" = public ] && I=$d/public
    for r in 1 2; do
      id="$item-r$r"
      [ -f "$OUT/attempts/$id.json" ] && continue
      $B nativetask run --task-file "$I/task.txt" --inputs-dir "$I" --ledger "$L/ledger.sqlite3" --attempt-id "$id" \
        --model "$M" --image ai4r:ccbench-native --execute --out "$OUT" > "$OUT/logs-$id.txt" 2>&1
      echo "$(basename "$OUT") $id exit=$?"
    done
  done
}
arm "$R/A-native-luna" gpt-6-luna public
arm "$R/A-verify-luna" gpt-6-luna "$V"
arm "$R/A-cclive-luna" gpt-6-luna "$R/A-cc/cc-live"
