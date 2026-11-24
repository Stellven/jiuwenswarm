#!/usr/bin/env bash
# Tiny checkpoints and the three tiny GGUF packs the scale wiring verifier reads (tiny_dir).
#   make_tiny_packs.sh TREE PY REF CONFIG OUT
# TREE   llama.cpp tree that already has your converter change (conversion/muse_spark.py)
# PY     python of the conversion venv (torch, safetensors, numpy, transformers)
# REF    dir with the real tokenizer files; CONFIG a Muse Spark config.json (tiny-random or real)
# OUT    output dir: OUT/ckpt/{bf16,nvfp4,deqref} and OUT/tiny-bf16.gguf, tiny-nvfp4-f32.gguf, tiny-deqref-f32.gguf
set -euo pipefail
TREE=${1:?tree}; PY=${2:?python}; REF=${3:?tokenizer dir}; CONFIG=${4:?config.json}; OUT=${5:?out dir}
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$OUT"
run() { nice -n 10 "$@"; }
run "$PY" "$HERE/tiny_checkpoint.py" --out "$OUT/ckpt" --tokenizer-dir "$REF" --config "$CONFIG"
export PYTHONDONTWRITEBYTECODE=1
# scale-free pack (no .scale tensors): the parity pack
run "$PY" "$TREE/convert_hf_to_gguf.py" "$OUT/ckpt/bf16" --outfile "$OUT/tiny-bf16.gguf" --outtype bf16 > "$OUT/conv-bf16.log" 2>&1
# NVFP4 pack through your converter; F32 elsewhere so only the experts differ from the reference
run "$PY" "$TREE/convert_hf_to_gguf.py" "$OUT/ckpt/nvfp4" --outfile "$OUT/tiny-nvfp4-f32.gguf" --outtype f32 > "$OUT/conv-nvfp4.log" 2>&1
# dequantized reference, all F32
run "$PY" "$TREE/convert_hf_to_gguf.py" "$OUT/ckpt/deqref" --outfile "$OUT/tiny-deqref-f32.gguf" --outtype f32 > "$OUT/conv-deqref.log" 2>&1
ls -la "$OUT"/*.gguf
