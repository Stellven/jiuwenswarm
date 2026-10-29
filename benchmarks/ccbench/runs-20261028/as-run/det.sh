#!/bin/sh
# Deterministic rebench at the merged HEAD, container mode (ai4r:cc-v1-baseline, repo read-only at /opt/ai4r).
# Usage: sh det.sh <repo> <out>
set -u
REPO=$1; OUT=$2; cd "$REPO"; B="sh scripts/ai4r-bench"
git rev-parse HEAD > "$OUT/HEAD.txt"; git status --porcelain --untracked-files=no >> "$OUT/HEAD.txt"
$B admission study --reps 10 --out "$OUT/C-admission" > "$OUT/C.log" 2>&1; echo "C exit=$?"
$B gatebench run --seeds 20 --out "$OUT/D-gatebench" > "$OUT/D.log" 2>&1; echo "D exit=$?"
$B trapcheck run --out "$OUT/B-ours" > "$OUT/B.log" 2>&1; echo "B-ours exit=$?"
$B nativeadmit cc_route --out "$OUT/A-cc" > "$OUT/A-cc.log" 2>&1; echo "A-cc exit=$?"
$B nativeadmit cc_fallback --out "$OUT/A-cc" > "$OUT/A-fallback.log" 2>&1; echo "A-fallback exit=$?"
