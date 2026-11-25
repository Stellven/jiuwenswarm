#!/bin/sh
# SAMPLE: the runs verify makes, by hand. Tiny pack only; never a full Muse pack. Capped and niced.
#   acceptance_run.sh STOCK_BIN CAND_BIN TINY_PACK [TEXT]
set -eu
STOCK=$1 CAND=$2 PACK=$3 TEXT=${4:-README.md}
P="The capital of France is"
run() { systemd-run --user --scope -q -p MemoryMax=16G -p MemorySwapMax=0 nice -n 10 "$@"; }

run "$STOCK/llama-simple" -m "$PACK" -n 32 "$P" > stock.out 2> stock.err
run "$CAND/llama-simple"  -m "$PACK" -n 32 "$P" > off.out   2> off.err
LLAMA_EXPERT_FILL=1 run "$CAND/llama-simple" -m "$PACK" -n 32 "$P" > on.out 2> on.err
LLAMA_EXPERT_FILL=1 LLAMA_EXPERT_FILL_SKIP_RESIDENT=0 run "$CAND/llama-simple" -m "$PACK" -n 32 "$P" > all.out 2> all.err
LLAMA_EXPERT_FILL=1 LLAMA_EXPERT_FILL_SKIP_RESIDENT=0 run "$CAND/llama-simple" -m "$PACK" -n 1 "$P" > pre.out 2> pre.err
cmp stock.out off.out && cmp stock.out on.out && cmp stock.out all.out && echo "parity: byte-identical"
grep -c "expert_fill" off.err || true          # want 0
grep "expert_fill: active" on.err              # want exactly one line
grep "expert_fill: stats" on.err all.err pre.err   # calls>0; all: reads>0 bytes_read>0; pre: calls=0

# values with the fill on every ubatch (prefill included); -lv 4 shows the library's info lines
run "$STOCK/llama-perplexity" -m "$PACK" -f "$TEXT" -c 128 -b 128 --chunks 4 2>&1 | grep "Final estimate"
LLAMA_EXPERT_FILL=1 LLAMA_EXPERT_FILL_MAX_TOKENS=0 LLAMA_EXPERT_FILL_SKIP_RESIDENT=0 \
  run "$CAND/llama-perplexity" -lv 4 -m "$PACK" -f "$TEXT" -c 128 -b 128 --chunks 4 2>&1 | grep -E "Final estimate|expert_fill"
