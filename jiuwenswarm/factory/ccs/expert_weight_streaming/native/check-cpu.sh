#!/usr/bin/env bash
# CPU fixtures only. OUT must be outside the source checkout.
set -euo pipefail
source_root=$(cd "$(dirname "$0")/../.." && pwd)
out=${1:?usage: check-cpu.sh EXTERNAL_OUTPUT_DIRECTORY}
mkdir -p "$out"
out=$(cd "$out" && pwd)
case "$out/" in "$source_root/"*) echo 'Output must be outside source' >&2; exit 2;; esac
unset LLAMA_EXPERT_RESIDENCY LLAMA_EXPERT_STREAMING LLAMA_EXPERT_WARM_SET
cmake -S "$source_root" -B "$out" -DGGML_CUDA=OFF -DGGML_NATIVE=OFF -DGGML_CPU_ARM_ARCH=armv8-a -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DLLAMA_BUILD_COMMON=OFF -DLLAMA_BUILD_TOOLS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_MTMD=OFF -DLLAMA_OPENSSL=OFF > "$out/configure.log" 2>&1
cmake --build "$out" --target ggml-cpu -j4 > "$out/build.log" 2>&1
c++ -std=c++17 -O1 -g -pthread -I"$source_root/ggml/src/ggml-cpu" "$source_root/tests/demo-expert-weights/test-residency.cpp" -o "$out/test-residency"
c++ -std=c++17 -O1 -g -pthread -I"$source_root/ggml/include" "$source_root/tests/demo-expert-weights/test-consumer.cpp" -L"$out/bin" -Wl,-rpath,"$out/bin" -lggml-cpu -lggml-base -o "$out/test-consumer"
timeout 60 "$out/test-residency" > "$out/residency.log" 2>&1
timeout 60 "$out/test-consumer" > "$out/consumer-f32.log" 2>&1
for format in iq1_m iq2_xxs iq2_xs q4_k q5_0 q8_0; do
 GGML_CPU_TILED_MM_FORCE=1 timeout 60 "$out/test-consumer" "$format" > "$out/consumer-$format.log" 2>&1
done
python3 - "$out" <<'PY' > "$out/loader-syntax.log" 2>&1
import json, subprocess, shlex, sys
from pathlib import Path
x=next(x for x in json.loads((Path(sys.argv[1])/'compile_commands.json').read_text()) if x['file'].endswith('/src/llama-model.cpp'))
a=shlex.split(x['command']); i=a.index('-o'); del a[i:i+2]; a[a.index('-c')]='-fsyntax-only'
subprocess.run(a,cwd=x['directory'],check=True)
print('PASS loader CPU syntax; no engine executable or hardware build')
PY
echo "PASS CPU lease, actual F32/packed readers, rollback and loader syntax; logs: $out"
