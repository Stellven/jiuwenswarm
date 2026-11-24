#!/usr/bin/env bash
# Scale-free parity: a pack WITHOUT .scale tensors must give byte-identical greedy output on stock and candidate.
#   parity.sh STOCK_BIN CAND_BIN PACK [N_PREDICT] [MEM_CAP]
# Exits 0 when stdout is byte-identical, 1 otherwise. Never runs uncapped on a shared host.
set -euo pipefail
STOCK=${1:?stock bin dir}; CAND=${2:?candidate bin dir}; PACK=${3:?pack}; N=${4:-32}; CAP=${5:-16G}
PROMPT="The capital of France is"
OUT=$(mktemp -d)
run() {  # bin label
  systemd-run --user --scope -q -p MemoryMax="$CAP" -p MemorySwapMax=0 \
    nice -n 10 "$1/llama-simple" -m "$PACK" -n "$N" "$PROMPT" > "$OUT/$2.out" 2> "$OUT/$2.err"
}
run "$STOCK" stock
run "$CAND" cand
if cmp -s "$OUT/stock.out" "$OUT/cand.out"; then
  echo "parity: identical ($(wc -c < "$OUT/cand.out") bytes) $OUT"
else
  echo "parity: DIFFERENT, see $OUT"; diff <(cat "$OUT/stock.out") <(cat "$OUT/cand.out") | head -20; exit 1
fi
