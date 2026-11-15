# Direct GPU application of three CC components

Executed directly on NVIDIA GB10 / SM121, without JiuwenSwarm, the CC Host, the
factory API, or the Strata inference executable. Three fresh GPU containers ran
the first implementation; three more ran a separate float32-scale follow-up.
All six exited successfully and were removed before the midnight deadline.

| GPU subtask | Baseline median | Candidate median | Local speed ratio |
| --- | ---: | ---: | ---: |
| Expert-cache dispatch, follow-up campaign | 2.3285 ms | 1.0339 ms | **2.25x** |
| Prefix projection reuse, follow-up campaign | 0.07751 ms | 0.005756 ms | **13.47x** |
| INT4 with reference float64 scales | 0.08670 ms | 0.24965 ms | **0.35x (slower)** |
| INT4 adapted to float32 GPU scales | 0.08655 ms | 0.09489 ms | **0.91x (still slower)** |

Times are medians of six CUDA-event observations per arm, from three fresh
processes with ABBA order inside each. Each timed observation averages repeated
operations after two warmups. Matvec/projection use 20 operations; expert dispatch
uses five complete trace replays. Host wall times are also retained. These are
short illustrative microbenchmarks, not confidence intervals or engine tokens/s.
The earlier campaign reproduced cache reuse at 2.38x and projection reuse at
13.37x. All individual measurements and paired ranges are in SUMMARY.json.

## What was actually applied

**Expert cache:** imported `expert_cache_lab/components.py` directly and applied
its byte-bounded LRU replay decisions to actual CUDA copies and matrix-vector
kernels. A deterministic 32-token trace selects six experts per token from 16
fixture experts; each expert has a 256x256 FP32 matrix. Eight cache slots fit
2 MiB. Baseline copies an expert before every invocation; candidate follows the
CC-produced load/slot decisions. Both execute all 192 expert operations.
Candidate performs 46 weight loads instead of 192, a 76.0% reduction, and all
49,152 output values match baseline exactly. Independent CPU spot checks also
pass. The data source is pinned host memory, not measured NVMe reads. Policy
computation is offline and excluded from these timings. This is not a replacement
for Strata's existing cache, nor a speed ratio against the Strata engine.

**KV-prefix reuse:** imported the KV CC's full-identity prefix matcher directly.
It matched 3,968 of 4,096 fixture tokens and returned zero reuse for a changed
model identity. CUDA computes a dense 128x128 projection representing concatenated
K/V features. Baseline recomputes all 4,096 positions; candidate retains the
previous prefix projection and computes only the 128 new positions. All 524,288
output values match exactly, and CPU spot checks pass. The zero-match fallback
also reproduces full recomputation. Timing excludes building the original cache,
CPU prefix matching, attention, decoding and KV allocator integration. The 13x
ratio concerns this projection only; it is not a 13x TTFT or inference gain.

**INT4:** imported the precision CC's actual custom codec. It generated packed
4-bit weights and float64 block scales for a 1024x1024 matrix. CUDA executes 16
vectors against either dequantized FP32 weights or fused INT4 dequantization.
The initial GPU adapter reproduces the quantized FP32 reference exactly, but is
about 2.88x slower. A separate follow-up converts scales to float32: about 2.63x
faster than the float64-scale kernel, but still approximately 9.6% more latency
than the FP32 reference. Its maximum output difference is 1.12e-7, below the
predeclared 1e-5 fixture tolerance. This is an additional approximation, not an
exact codec change. Both paths use straightforward reference kernels, not cuBLAS
or optimized native Strata kernels. The FP32 baseline is already dequantized
from INT4; no language-model quantization quality is established.

## Correctness and interpretation

All GPU reference comparisons cover complete output arrays. Independent CPU
spot checks use higher-precision accumulations; maximum baseline error is about
1.10e-8 across these tests. No nonfinite outputs, OOMs or CUDA errors occurred.
A compile warning caught a macro variable-shadowing bug before execution; the
initial warning log is retained and the corrected code was compiled before any
GPU measurements. Both CUDA source variants and all results remain separate.

The tests show that the cache and prefix components can drive correct CUDA work,
and expose a concrete INT4 implementation bottleneck. They do not establish that
these components improve the current Strata engine. Next useful steps are a
native cache/readiness integration with actual routing traces, correct model KV
state binding, and a vectorized/tensor-core-compatible low-bit kernel. Keep model
correctness and full-workload throughput tests separate from these small probes.

## Reproduce and evidence

Each campaign directory contains CUDA source, a compiled ARM64 SM121 binary,
frozen binary fixtures produced by the CC components, source hashes, exact Docker
commands, created/final container inspections, stdout/stderr, cleanup receipts,
and CUDA/host timings. `RUN-CONTRACT.json` pins source and binary identities.
`prepare.py` in v1 shows how the three packages generated the fixtures; it assumes
the original workspace. Frozen fixtures are sufficient to reproduce GPU work
elsewhere without any model weights or JiuwenSwarm installation.

Compile with an existing CUDA 13 ARM64 toolchain:

```sh
nvcc -O3 -std=c++17 -arch=sm_121 --fmad=false gpu_components.cu -o gpu_components
./gpu_components /absolute/path/to/the/campaign-directory
```

The recorded runs used the existing pinned ARM64 CUDA runtime image, a read-only
fixture mount, no network, four CPU cores, 4 GiB RAM and no extra swap. No global
dependencies were installed. The root summarizer independently checks source
hashes and runtime boundaries before computing metrics. Previous CC handoffs and
seals are unchanged; this is a GPU evidence supplement for the exact component
source hashes in inputs.json, not automatic production admission.
