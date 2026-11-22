#!/usr/bin/env bash
# Build llama-server for DGX Spark (GB10: aarch64, CUDA 13, sm_121) either
# natively on an arm64 host or as a cross build on an x86_64 host.
#
#   build-llama-server.sh --src DIR --build DIR [--out DIR] [options]
#
# Options
#   --src DIR          llama.cpp checkout (required)
#   --build DIR        persistent build dir (re-used for incremental builds; required)
#   --out DIR          output app dir (default: <build>/app)
#   --cross            force the aarch64 cross toolchain (default: auto, on when host != aarch64)
#   --native           force a native build
#   --cpu-only         -DGGML_CUDA=OFF
#   --archs LIST       CMAKE_CUDA_ARCHITECTURES (default: 121-real)
#   -j|--jobs N        parallel jobs (default: nproc, capped by $MAX_JOBS if set)
#   --generator G      ninja | make (default: ninja if found)
#   --no-ccache        do not use ccache even if found
#   --clean            delete the build dir first
#   --target T         build target (default: llama-server)
#   --bundle-cuda      also copy libcudart/libcublas/libcublasLt into app/ (large)
#   --nice N           run configure/build under `nice -n N`
#   -D...              any extra cmake definition (repeatable)
#
# Cross-build environment (see README.md): CUDA_TOOLKIT_ROOT (default /usr/local/cuda,
# must contain an x86_64 nvcc and targets/sbsa-linux), CROSS_TRIPLE (aarch64-linux-gnu),
# CROSS_TOOLCHAIN_BIN, CROSS_SYSROOT.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
src="" build="" out="" mode=auto cuda=ON archs="121-real" jobs="" gen="" use_ccache=1
clean=0 target=llama-server bundle_cuda=0 nice_n="" extra=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --src) src="$2"; shift 2;;
    --build) build="$2"; shift 2;;
    --out) out="$2"; shift 2;;
    --cross) mode=cross; shift;;
    --native) mode=native; shift;;
    --cpu-only) cuda=OFF; shift;;
    --archs) archs="$2"; shift 2;;
    -j|--jobs) jobs="$2"; shift 2;;
    --generator) gen="$2"; shift 2;;
    --no-ccache) use_ccache=0; shift;;
    --clean) clean=1; shift;;
    --target) target="$2"; shift 2;;
    --bundle-cuda) bundle_cuda=1; shift;;
    --nice) nice_n="$2"; shift 2;;
    -D*) extra+=("$1"); shift;;
    -h|--help) sed -n '2,30p' "$0"; exit 0;;
    *) echo "unknown argument: $1" >&2; exit 2;;
  esac
done
[[ -n "$src" && -n "$build" ]] || { echo "--src and --build are required" >&2; exit 2; }
src="$(cd "$src" && pwd)"
mkdir -p "$build"; build="$(cd "$build" && pwd)"
out="${out:-$build/app}"

host_arch="$(uname -m)"
if [[ $mode == auto ]]; then
  if [[ $host_arch == aarch64 || $host_arch == arm64 ]]; then mode=native; else mode=cross; fi
fi
jobs="${jobs:-$(nproc)}"
if [[ -n "${MAX_JOBS:-}" && $jobs -gt $MAX_JOBS ]]; then jobs=$MAX_JOBS; fi

if [[ -z "$gen" ]]; then command -v ninja >/dev/null && gen=ninja || gen=make; fi
case "$gen" in ninja) generator=Ninja;; make) generator="Unix Makefiles";; *) echo "bad generator $gen" >&2; exit 2;; esac

cuda_root="${CUDA_TOOLKIT_ROOT:-/usr/local/cuda}"
flags=(
  -DCMAKE_BUILD_TYPE=Release
  -DGGML_CUDA="$cuda"
  -DGGML_NATIVE=OFF
  -DGGML_CPU_ARM_ARCH=armv8.2-a+dotprod+fp16+i8mm
  -DGGML_OPENMP=OFF
  -DLLAMA_BUILD_TESTS=OFF
  -DLLAMA_BUILD_EXAMPLES=OFF
  -DLLAMA_BUILD_SERVER=ON
  -DLLAMA_OPENSSL=OFF
  -DLLAMA_CURL=OFF
  # everything lands in bin/ next to the executable; make the RPATH relocatable
  -DCMAKE_BUILD_RPATH_USE_ORIGIN=ON
)
[[ $cuda == ON ]] && flags+=(-DCMAKE_CUDA_ARCHITECTURES="$archs")
if [[ $mode == cross ]]; then
  flags+=(-DCMAKE_TOOLCHAIN_FILE="$here/aarch64-cuda13.toolchain.cmake")
elif [[ $cuda == ON ]]; then
  flags+=(-DCMAKE_CUDA_COMPILER="$cuda_root/bin/nvcc")
fi
ccache_bin=""
if [[ $use_ccache == 1 ]] && command -v ccache >/dev/null; then
  ccache_bin="$(command -v ccache)"
  flags+=(-DCMAKE_C_COMPILER_LAUNCHER="$ccache_bin" -DCMAKE_CXX_COMPILER_LAUNCHER="$ccache_bin")
  [[ $cuda == ON ]] && flags+=(-DCMAKE_CUDA_COMPILER_LAUNCHER="$ccache_bin")
else
  flags+=(-DGGML_CCACHE=OFF)
fi
flags+=("${extra[@]}")

run() { if [[ -n "$nice_n" ]]; then nice -n "$nice_n" "$@"; else "$@"; fi; }
now() { date +%s.%N; }

[[ $clean == 1 ]] && rm -rf "$build" && mkdir -p "$build"
# a generator switch in an existing build dir is not allowed by cmake
if [[ -f "$build/CMakeCache.txt" ]] && ! grep -q "^CMAKE_GENERATOR:INTERNAL=$generator\$" "$build/CMakeCache.txt"; then
  echo "build dir was configured with another generator; use --clean or another --build" >&2; exit 2
fi

echo "== mode=$mode host=$host_arch cuda=$cuda archs=$archs gen=$gen jobs=$jobs ccache=${ccache_bin:-no}"
t0=$(now)
run cmake -S "$src" -B "$build" -G "$generator" "${flags[@]}"
t1=$(now)
run cmake --build "$build" --target "$target" -j "$jobs"
t2=$(now)

# ---- package: executable + the non-system shared libs it needs ----
rm -rf "$out"; mkdir -p "$out"
bin="$build/bin"
cp -a "$bin/$target" "$out/"
readelf_bin="readelf"; command -v readelf >/dev/null || readelf_bin="${CROSS_TRIPLE:-aarch64-linux-gnu}-readelf"
needed() { "$readelf_bin" -d "$1" 2>/dev/null | sed -n 's/.*(NEEDED).*\[\(.*\)\]/\1/p'; }
declare -A seen=()
queue=("$out/$target")
cuda_libs=()
while [[ ${#queue[@]} -gt 0 ]]; do
  f="${queue[0]}"; queue=("${queue[@]:1}")
  for lib in $(needed "$f"); do
    [[ -n "${seen[$lib]:-}" ]] && continue; seen[$lib]=1
    if [[ -e "$bin/$lib" ]]; then
      cp -aL "$bin/$lib" "$out/$lib"; queue+=("$out/$lib")
    elif [[ $lib == libcudart* || $lib == libcublas* ]]; then
      cuda_libs+=("$lib")
      if [[ $bundle_cuda == 1 ]]; then
        for d in "$cuda_root/targets/sbsa-linux/lib" "$cuda_root/lib64"; do
          [[ -e "$d/$lib" ]] && { cp -aL "$d/$lib" "$out/$lib"; break; }
        done
      fi
    fi
  done
done
t3=$(now)

# ---- build.json ----
ver() { "$@" 2>/dev/null | head -1 || true; }
if [[ $mode == cross ]]; then cxx="${CROSS_TOOLCHAIN_BIN:+$CROSS_TOOLCHAIN_BIN/}${CROSS_TRIPLE:-aarch64-linux-gnu}-g++"; else cxx="${CXX:-g++}"; fi
export BJ_HOST_ARCH="$host_arch" BJ_MODE="$mode" BJ_JOBS="$jobs" BJ_NPROC="$(nproc)" BJ_GEN="$gen" \
  BJ_CCACHE="${ccache_bin}" BJ_CMAKE="$(ver cmake --version)" BJ_GENVER="$(ver $([[ $gen == ninja ]] && echo ninja || echo make) --version)" \
  BJ_CXX="$(ver "$cxx" --version)" BJ_NVCC="$([[ $cuda == ON ]] && "$cuda_root/bin/nvcc" --version 2>/dev/null | tail -1 || true)" \
  BJ_CCV="$([[ -n $ccache_bin ]] && ver ccache --version || true)" \
  BJ_SRC="$src" BJ_REV="$(git -C "$src" rev-parse HEAD 2>/dev/null || true)" BJ_TARGET="$target" \
  BJ_T0="$t0" BJ_T1="$t1" BJ_T2="$t2" BJ_T3="$t3" BJ_OUT="$out" BJ_CUDA_LIBS="${cuda_libs[*]:-}" \
  BJ_FILE="$(file -b "$out/$target" 2>/dev/null || true)"
printf '%s\n' "${flags[@]}" > "$out/.flags"
python3 - <<'PY'
import hashlib, json, os
e = os.environ
out = e["BJ_OUT"]
f = lambda k: float(e[k])
exe = os.path.join(out, e["BJ_TARGET"])
flags = open(os.path.join(out, ".flags")).read().splitlines()
os.remove(os.path.join(out, ".flags"))
doc = {
    "target": e["BJ_TARGET"], "mode": e["BJ_MODE"], "host_arch": e["BJ_HOST_ARCH"],
    "host_nproc": int(e["BJ_NPROC"]), "jobs": int(e["BJ_JOBS"]), "generator": e["BJ_GEN"],
    "ccache": e["BJ_CCACHE"] or None, "source": e["BJ_SRC"], "source_rev": e["BJ_REV"],
    "toolchain": {"cmake": e["BJ_CMAKE"], "generator": e["BJ_GENVER"], "cxx": e["BJ_CXX"],
                  "nvcc": e["BJ_NVCC"] or None, "ccache": e["BJ_CCV"] or None},
    "cmake_flags": flags,
    "seconds": {"configure": round(f("BJ_T1") - f("BJ_T0"), 2), "build": round(f("BJ_T2") - f("BJ_T1"), 2),
                "package": round(f("BJ_T3") - f("BJ_T2"), 2), "total": round(f("BJ_T3") - f("BJ_T0"), 2)},
    "executable": {"file": e["BJ_FILE"], "sha256": hashlib.sha256(open(exe, "rb").read()).hexdigest()},
    "bundled_libs": sorted(x for x in os.listdir(out) if ".so" in x),
    "cuda_runtime_libs_expected": e["BJ_CUDA_LIBS"].split(),
}
json.dump(doc, open(os.path.join(out, "build.json"), "w"), indent=2)
print(json.dumps(doc["seconds"]))
PY
echo "== app: $out"
