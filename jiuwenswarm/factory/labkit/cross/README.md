# Cross-compiling llama-server for DGX Spark (GB10) on x86_64

Files:

- `aarch64-cuda13.toolchain.cmake`: the CMake toolchain for x86_64 -> aarch64 Linux + CUDA 13 (`targets/sbsa-linux`). It is configured only through env/cache variables: `CROSS_TRIPLE` (default `aarch64-linux-gnu`), `CROSS_TOOLCHAIN_BIN`, `CROSS_SYSROOT`, `CUDA_TOOLKIT_ROOT` (default `/usr/local/cuda`) and `CUDA_TARGET_NAME` (default `sbsa-linux`).
- `build-llama-server.sh`: a single build entry point. On aarch64 it builds natively; on x86_64 (or with `--cross`) it uses the toolchain. It uses Ninja and ccache when found and keeps a persistent `--build` dir. It writes `app/` containing `llama-server`, the llama/ggml shared libs it needs (found by walking `DT_NEEDED`) and `build.json`. `build.json` records host arch, nproc, -j, tool versions, cmake flags, seconds per phase (configure/build/package), the sha256 of the executable, and the CUDA runtime libs the target must provide.

The flags are the factory's `spark_engine.LLAMA_FLAGS`: Release, `GGML_CUDA=ON`, `GGML_NATIVE=OFF`, `GGML_CPU_ARM_ARCH=armv8.2-a+dotprod+fp16+i8mm`, and no OpenMP/tests/examples/OpenSSL/curl. One deliberate difference: the default `CMAKE_CUDA_ARCHITECTURES` is `121-real`, while the engine uses `121-real;121-virtual`. Pass `--archs '121-real;121-virtual'` to match the engine; it adds about 6% (see the timings). ggml rewrites `121-real` to `121a-real` both natively and in the cross build. The script adds `-DCMAKE_BUILD_RPATH_USE_ORIGIN=ON`, so the binary carries `RUNPATH $ORIGIN` and `app/` can be copied anywhere.

## Usage

```bash
# arm64 lab (native)
nice -n 10 ./build-llama-server.sh --src ~/llama.cpp --build ~/llama-build -j 12
# x86_64 host (cross), after the setup below
./build-llama-server.sh --src ~/llama.cpp --build ~/llama-xbuild          # --cross is implied on x86_64
./build-llama-server.sh --src ~/llama.cpp --build ~/llama-xbuild-cpu --cpu-only
```

Other options: `--generator ninja|make`, `--no-ccache`, `--clean`, `--target`, `--bundle-cuda` (also copies libcudart/libcublas/libcublasLt, about 700 MB), `--nice N` and extra `-D...` definitions. Re-running with the same `--build` gives an incremental build. To run the result on the Spark, copy `app/` there. CUDA 13.x `libcudart.so.13`, `libcublas.so.13` and `libcublasLt.so.13` must come from the host (`/usr/local/cuda/lib64`) or from the runtime image; the factory llamacpp images have them.

```bash
LD_LIBRARY_PATH=/usr/local/cuda/lib64 app/llama-server --list-devices
docker run --rm --gpus all -v $PWD/app:/x:ro -e LD_LIBRARY_PATH=/x:/usr/local/nvidia/lib:/usr/local/nvidia/lib64 \
  --entrypoint /x/llama-server factory/llamacpp:deepseek-stock-20261120 --list-devices
```

## x86_64 cross host setup

### A. With root (standard; not run here, because the test host had no passwordless sudo)

```bash
sudo apt-get install -y cmake ninja-build ccache gcc-aarch64-linux-gnu g++-aarch64-linux-gnu
# NVIDIA CUDA repo for ubuntu2404 x86_64
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb && sudo apt-get update
sudo apt-get install -y cuda-nvcc-13-0 cuda-cudart-dev-13-0 cuda-cross-sbsa-13-0
#   cuda-cross-sbsa-13-0 provides /usr/local/cuda-13.0/targets/sbsa-linux (cudart, cublas, stubs, headers)
```

Then `CUDA_TOOLKIT_ROOT=/usr/local/cuda-13.0` (or the `/usr/local/cuda` symlink). Leave `CROSS_SYSROOT`/`CROSS_TOOLCHAIN_BIN` unset; the Ubuntu cross gcc finds `/usr/aarch64-linux-gnu` itself.

### B. Without root (what was actually run, in WSL2 Ubuntu 24.04)

Everything installs under `~/xbuild` (about 2.5 GB including 1.3 GB of downloads; 290 s on this connection):

1. `python3 -m venv ~/xbuild/tools/venv && ~/xbuild/tools/venv/bin/pip install cmake ninja` (gives cmake 4.4.5, ninja 1.13.2).
2. ccache: the static `ccache-4.11.3-linux-x86_64.tar.xz` from the GitHub releases.
3. Cross gcc 13.3: `apt-get download` needs no root. Download `gcc-aarch64-linux-gnu g++-aarch64-linux-gnu cpp-aarch64-linux-gnu binutils-aarch64-linux-gnu cpp-13-aarch64-linux-gnu gcc-13-aarch64-linux-gnu g++-13-aarch64-linux-gnu gcc-13-aarch64-linux-gnu-base libc6-arm64-cross libc6-dev-arm64-cross linux-libc-dev-arm64-cross libgcc-13-dev-arm64-cross libgcc-s1-arm64-cross libstdc++-13-dev-arm64-cross libstdc++6-arm64-cross libgomp1-arm64-cross libatomic1-arm64-cross libasan8-arm64-cross libhwasan0-arm64-cross libitm1-arm64-cross liblsan0-arm64-cross libtsan2-arm64-cross libubsan1-arm64-cross`, then run `dpkg -x <deb> ~/xbuild/tc` on each.
4. CUDA 13.0 from NVIDIA's redist tarballs (`https://developer.download.nvidia.com/compute/cuda/redist/`, versions from `redistrib_13.0.2.json`). They are laid out like a normal toolkit in `~/xbuild/cuda-13.0`:
   - x86_64 `cuda_nvcc 13.0.88`, `cuda_crt`, `libnvvm`, `cuda_cudart 13.0.96` and `cuda_cccl` go into `targets/x86_64-linux`, with `include` and `lib` symlinked at the top.
   - sbsa `cuda_cudart`, `cuda_cccl`, `cuda_crt`, `libcublas 13.1.0.3` and the `include/` of sbsa `cuda_nvcc` (for `fatbinary_section.h`) go into `targets/sbsa-linux`.

   This matches the Spark (nvcc 13.0.88, cudart 13.0.96).
5. Environment:
   ```bash
   export PATH=~/xbuild/tools/venv/bin:~/xbuild/tools:~/xbuild/tc/usr/bin:$PATH
   export LD_LIBRARY_PATH=~/xbuild/tc/usr/lib/x86_64-linux-gnu   # libopcodes/libbfd of the cross binutils
   export CROSS_TOOLCHAIN_BIN=~/xbuild/tc/usr/bin CROSS_SYSROOT=~/xbuild/tc CUDA_TOOLKIT_ROOT=~/xbuild/cuda-13.0
   export CCACHE_DIR=~/xbuild/ccache CCACHE_BASEDIR=~/xbuild
   ```
   On WSL, also remove the `/mnt/c/...` entries from `PATH`. Every CMake `find_*` stats each of them over 9p, which made configure take more than 5 minutes; with them removed it takes 4 s.
6. Source: a full-history clone at `9048bad8d`. A shallow clone does **not** work: see the caveats.

## Measured times (llama.cpp 9048bad8d, target llama-server, 121-real, wall seconds = configure + build)

Native: DGX Spark GB10 with 20 cores (10 Cortex-X925 + 10 Cortex-A725), `nice -n 10`, `-j12`, cmake 3.28.3, gcc 13.3, nvcc 13.0.88.
Cross: x86_64 Intel i7-1260P laptop under WSL2. **WSL is capped at 2 vCPU / 3 GB RAM by the user's `.wslconfig`**, so it ran at `-j2`. cmake 4.4.5, aarch64-linux-gnu-g++ 13.3, nvcc 13.0.88.

| Scenario | Spark native, -j12 | x86 cross (WSL, 2 vCPU), -j2 |
|---|---:|---:|
| Clean, Ninja, no ccache / cold ccache | **163.8** (ccache cold: 166.4) | **1697.0** (cold ccache, 320/320 misses) |
| Clean, Make | 180.3 | not run |
| Clean, Ninja, `121-real;121-virtual` | 173.0 (+6%) | not run |
| Clean, CPU-only (`GGML_CUDA=OFF`) | 35.5 | 372.2 (no ccache) |
| Clean build in a new dir, **warm ccache** | **6.1** (320/320 hits) | 76.3 (300/320 hits; the misses came from a build-number change between runs) |
| Edit `src/llama-model.cpp` (real content change) | 6.3 (ccache) / 6.5 (touch, Ninja) / 6.5 (touch, Make) | 15.8 |
| Edit `ggml/src/ggml-cuda/mmq.cu` | 4.9 (ccache) / 4.8 (touch, Ninja) / 5.1 (touch, Make) | 11.1 |
| Touch `src/llama-model.h` | 9.7 | not run |
| Touch `ggml/src/ggml-cuda/common.cuh` (all CUDA objects) | 130.8 | not run (roughly the CUDA part of a clean build) |
| No-op rebuild | 0.4 | 1.9 (touch only, so ccache hit) |

Lab-side numbers measured separately with `jiuwenswarm/factory/lab_build.py` warm slots on the Spark (same commit, sm_121-real, Ninja, -j12, expert-weight-cache diff):

- cold slot: 160 s compile, 186 s total including 22 s for the image;
- warm slot, next diff: 4.1 s compile;
- warm slot with the layered image context reused: 4.8 s total.

Verification of the cross-built binary (built on WSL, copied to the Spark):

```
$ file llama-server
ELF 64-bit LSB pie executable, ARM aarch64, version 1 (SYSV), dynamically linked, interpreter /lib/ld-linux-aarch64.so.1, ...
$ readelf -d llama-server | grep RUNPATH        ->  [$ORIGIN:]
$ ldd: libggml-cuda.so.1 => ./libggml-cuda.so.1, libcudart.so.13 / libcublas.so.13 / libcublasLt.so.13 => /usr/local/cuda/lib64, libcuda.so.1 => /lib/aarch64-linux-gnu
$ llama-server --version                  (host)
version: 1.0.0-dev (build 12493, commit 9048bad8d)
built with GNU 13.3.0 for Linux aarch64
$ llama-server --list-devices             (host, and inside factory/llamacpp:deepseek-stock-20261120)
Available devices:
  CUDA0: NVIDIA GB10 (124608 MiB, 120076 MiB free)
```

The bundled libs (`libggml-base/cpu/cuda`, `libggml`, `libllama`, `libllama-common`, `libllama-server-impl`, `libmtmd`) are within 0.2% of the native build's sizes. `libggml-cuda.so.1` is 49.3 MB cross vs 49.4 MB native, with the same toolkit headers apart from the cublas minor version.

## What makes arm64 builds fast (ranked by measured effect)

1. **Keep the build dir (warm slot)**: 164 s down to 4-10 s for a `.cpp`/`.cu` edit. Only shared CUDA headers (`common.cuh`, `mmq.cuh`, `fattn-*.cuh`) trigger a near-full CUDA rebuild (131 s). This is the dominant lever. `lab_build.py`'s warm slots already exploit it (4.1 s).
2. **ccache on the Spark**: the aarch64 static binary from the ccache GitHub releases needs no sudo. Verify the archive against GitHub's sha256 asset digest. Cold costs +1.6% (166 vs 164 s). A clean build in a *new* dir then takes 6.1 s instead of 164 s, so new slots, `--clean`, flag-only reconfigures that do not change compile lines, and switching back to an earlier diff become nearly free. The cache for one configuration is 49 MB. Set `CCACHE_BASEDIR` to the slot root so different slot paths share hits. There is no pip wheel for ccache.
3. **Ninja instead of Make**: 9% faster clean build (164 vs 180 s), about the same incremental.
4. **Single real arch**: `121-real` instead of `121-real;121-virtual` saves 6% (10 s) per clean build and on every CUDA recompile. Keep `-virtual` only if a PTX fallback is actually needed (GB10 is sm_121, and the image always runs on it).
5. **Build only the `llama-server` target**: its closure is 320 objects vs 352 for `all` (with tools on), about 10% less. The script does this.
6. **Leave `GGML_CUDA_FA_ALL_QUANTS` OFF** (the default; not changed or measured here). Turning it on multiplies the fattn template instances, which are the slowest CUDA objects.
7. **-j**: the Spark has 20 cores, and the lab policy caps shared builds at -j12. The CUDA template instances parallelise well, so most of the 164 s is CUDA compile that scales with -j.

## Verdict: cross-compile or let the arm64 lab build?

**Let the arm64 lab build.** The Spark compiles a clean llama-server in 164 s at -j12, and in 4-6 s from a warm slot or warm ccache. The lab's own warm slots measure 4.1 s compile / 4.8 s total.

Cross-compiling **works** and produces a binary that runs on the GB10 in the factory runtime image. However, on this x86 host it took 1697 s (28 min) cold, 15.8 s for a `.cpp` edit and 76 s even with warm ccache. That host is a 2-vCPU WSL VM; per CUDA job it is about 1.7x slower than a Spark core (3385 vs about 1930 core-seconds for the same 320 objects). Even uncapped at 12 jobs with perfect scaling, this laptop would need about 280 s, still slower than the Spark's 164 s. Cross only pays off on a big x86 server (32+ fast cores) used for cold/clean builds, while the Spark is busy or unavailable, or for CI that has no arm64 hardware. Any per-diff loop still belongs in a warm slot on the Spark: the ~70 MB `app/` copy plus an image layer cost about as much as the native incremental compile.

Useful cross roles in the factory:
- compile-check a candidate diff (configure + compile errors) before it takes a lab slot;
- run cold rebuilds (new llama.cpp commit, flag changes) off the shared Spark;
- provide a CPU-only aarch64 fallback build.

## Caveats

- **The build downloads the web UI**: llama-server's build fetches `dist.tar.gz` from Hugging Face (`ggml-org/llama-ui`, version `b<LLAMA_BUILD_NUMBER>`, falling back to `latest`) and needs network. The build number comes from `git rev-list --count`. A shallow clone gives build 1 and an asset set that fails `ui-assets.cmake`'s check ("missing required asset(s)"). Use a full clone (`git fetch --unshallow`), or pass the real `-DLLAMA_BUILD_NUMBER=12493` plus pre-fetched assets for offline builds.
- `FindCUDAToolkit` runs before `enable_language(CUDA)` in ggml-cuda and parses nvcc's default (x86_64) include dir into `CUDA::cudart`. The x86_64 headers must therefore exist (as they do in a normal toolkit), and are identical to the sbsa ones. Because of this, the cross build prints harmless `-Wunused-parameter` warnings from `cuda_fp4.hpp` (the sbsa include comes in via nvcc's `-I` rather than `-isystem`).
- `libggml-cuda.so` needs `libcuda.so.1`. The toolchain exposes the toolkit stub as `<build>/_cuda_stub_soname/libcuda.so.1` for `-rpath-link` only; the real driver is used at runtime.
- The binary needs a CUDA 13.x runtime (`libcudart.so.13`, `libcublas*.so.13`) on the target; it was tested with the host's 13.0 and the image's 13.4. Use `--bundle-cuda` to ship them.
- `build.json` records absolute paths (source, toolchain file) of the build host; they are informational only.
- ccache hits require identical compile lines, so a different build number (`LLAMA_BUILD_NUMBER`/commit) or a different checkout path without `CCACHE_BASEDIR` turns hits into misses.
- `touch` is not an edit when ccache is on (content unchanged means a hit). The edit rows above use a real one-line change.
