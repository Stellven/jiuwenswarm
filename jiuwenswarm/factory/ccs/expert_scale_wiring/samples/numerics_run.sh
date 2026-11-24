#!/usr/bin/env bash
# SAMPLE (labelled): the numerics runs on the tiny packs, capped and niced. Adapt paths.
set -euo pipefail
CAND=${1:?candidate bin}; STOCK=${2:?stock bin}; TINY=${3:?tiny dir}; WORK=${4:?work dir}; TEXT=${5:?text file}
HERE=$(cd "$(dirname "$0")/../helpers" && pwd)
cap() { systemd-run --user --scope -q -p MemoryMax=16G -p MemorySwapMax=0 nice -n 10 "$@"; }
mkdir -p "$WORK"

# 1. scale-free parity (must be byte-identical)
bash "$HERE/parity.sh" "$STOCK" "$CAND" "$TINY/tiny-bf16.gguf"

# 2. KLD of the NVFP4 pack against the dequantized reference (CPU)
python3 "$HERE/kld_compare.py" --bin "$CAND" --ref "$TINY/tiny-deqref-f32.gguf" --model "$TINY/tiny-nvfp4-f32.gguf" \
    --text "$TEXT" --work "$WORK/kld" --threads 8

# 3. one layer slice: expert matmuls and block output of the first quantized layer
for p in nvfp4-f32 deqref-f32; do
  cap "$CAND/llama-eval-callback" -m "$TINY/tiny-$p.gguf" -p "The capital of France is" -n 1 -t 8 > "$WORK/cb-$p.log" 2>&1
done
python3 "$HERE/slice_compare.py" "$WORK/cb-nvfp4-f32.log" "$WORK/cb-deqref-f32.log" --layer 1
# CUDA builds: repeat 2 with and without GGML_CUDA_MMQ_PREC=q8 and record which activation path you measured.
