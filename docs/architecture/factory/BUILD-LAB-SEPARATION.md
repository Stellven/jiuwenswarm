# Separate factory/build hosting from Spark qualification

The operator clarified that the new Intel machine hosts the factory and builds;
Sparks are dedicated labs. Use Ubuntu 24.04 LTS amd64 on the expected Intel
13th/14th-generation host. Its optional RTX GPUs are not needed to compile the
Spark target. They require a separate target profile if used for other tests.
Model weights remain on the labs. This investigation used retained records and
source inspection only; no new build or GPU work was performed for it.

## Measured build bottleneck

Three round-2 builds on Spark used the same pinned native toolchain and GGML
dependency, eight compiler workers, a 16 GiB container cap and all 170 Ninja
steps. None found an existing CMake cache:

| Build attempt | Source commit | Total seconds | Configure | Compile | Docker packaging |
| --- | --- | ---: | ---: | ---: | ---: |
| `9861542e467e46b895a1de2243c18be9` | `a9b7a7ad7560a6b30d4c76b093f8a878066e811d` | 159.13 | 2.15 | 134.59 | 18.75 |
| `ec99d5a626574298a366be460f77f53b` | `f3c793071dfa5b8599fa73abadfefa9835c0e8cd` | 166.34 | 2.16 | 142.93 | 17.66 |
| `7af5ff2406af4b5ba530a7fe74de389c` | `231b10b9780c8fb678d130a5d23676660e798add` | 166.82 | 2.21 | 142.75 | 18.35 |

Across these runs, compilation consumed approximately 85% of build wall time,
packaging 11%, configuration 1.3%. Total build time was 492.29 seconds. These
figures exclude queue waiting, agent deliberation, GPU measurement and any
future inter-machine delivery. Eliminating packaging alone cannot eliminate
the dominant compiler cost. No speedup on Intel or from cross compilation has
yet been measured in these records.

The three `:build-record` artifacts were checked against their stored SHA256:

```text
9861542e... a2bc0a095205f2172a759a6d9d626bf4a89720a786687f15eb51f38bea0827b3
ec99d5a6... 54520e3ed58ff8179b99d8d418018a30f69271700e091d31a1c3173278c2fe66
7af5ff24... f7701b4aa5a22efa277b2f9e8b1b313cbbf2cdba5ff33ce9043024c17fbd46ed
```

They reside in task `native-throughput-goal-002`, store
`/home/user2/software-factory-spark-20261113/native-throughput-round2-20261116/factory`.
All three frozen GGML tree inventories have the same SHA256:
`322862d213ed722d6500da0b58a1b7fffff53aa0de77d7f2e8ba685c653a0d9f`.

## Why the current cache does not help iterative changes

`spark_engine.py` creates an immutable source/dependency snapshot per attempt.
Its cache key includes the source commit/tree and all flags, including
`-DSTRATA_GGML_DIR=<attempt-output>/frozen-dependency`. Consequently every source
revision gets a fresh cache; even an identical revision submitted as a distinct
attempt gets a different absolute dependency path in its key. This latter
behavior is a code-derived defect in reuse, not a measured repeat-build result.
The observed `build_cache_present=false` and complete 170-step logs are
consistent with this design. The unchanged GGML dependency is recompiled.

Prioritize cache design before assuming a faster machine solves the loop:

1. Give immutable snapshots stable content-addressed storage and stable paths
   inside build containers, such as `/src` and `/deps/ggml`. Do not compile from
   a concurrently editable agent checkout.
2. Separate build provenance from reuse keys. The receipt still records exact
   source commit/tree/content, dependency hash, compiler/sysroot image, recipe,
   flags and output hashes. A compiler cache reuses matching translation units
   across revisions only after hashing their real inputs; it must never treat
   an old final binary as the new revision's output.
3. Use a compiler cache with explicitly validated CUDA support and namespace it
   by target/toolchain/flags. Retain cache hit/miss and compiler wall timings.
   Alternatively maintain a locked incremental workspace for a compatible
   configuration, materializing the selected immutable tree before building.
   Test header/dependency/flag changes and concurrent builds for stale reuse.
4. Add a reusable immutable GGML build keyed by its source/toolchain/flags/ABI
   only if the CMake dependency graph can consume it without losing correctness.
   Do not bypass transitive dependencies to gain a nominal cache hit.

Each packaged app directory is about 735 MB, while the executable is about
42.5 MB. The remainder is the same CUDA runtime/cuBLAS libraries, including
`libcublasLt.so.13` at 629,945,952 bytes. Current Dockerfile copies the app and
those libraries together, so a binary change invalidates that COPY layer.
Create a pinned target-runtime layer containing unchanged libraries, then a
small executable layer. Keep library hashes and base digest in provenance.
Images total approximately 3.099 GB locally; this is not compressed network
transfer size. A shared registry/content-addressed transfer should reuse common
layers rather than exporting the whole image for every experiment.

## Builder choices

| Choice | Benefits | Required work / limitation |
| --- | --- | --- |
| Native ARM64 build worker, no GPU | Closest to the exercised compiler/container recipe; GPU is unnecessary for code generation | Needs an ARM64 worker, distinct build admission and remote artifact delivery. Current wrapper still incorrectly assumes a local NVIDIA device. |
| Intel x86-64, true ARM64-SBSA cross compiler | Matches expected IT hardware; compiler runs natively on Intel and emits ARM64 host code plus SM121 GPU code | Needs pinned cross GCC/G++, CUDA13.0 cross-SBSA target libraries, compatible sysroot, explicit CMake toolchain and target dependency inspection; qualification still runs on Spark. |
| ARM64 image under QEMU on Intel | Can help diagnose portability when no cross recipe exists | Not the recommended speed strategy. Docker warns that emulation is significantly slower for compilation/compression; no speed measurement for this project is available. Current wrapper explicitly rejects emulation. |

Docker documents native nodes, cross compilation and emulation as separate
strategies; `--platform linux/arm64` alone does not make a compiler cross-native.
[Docker multi-platform build documentation](https://docs.docker.com/build/building/multi-platform/).

NVIDIA's CUDA13.0 guide supports ARM64-SBSA cross development from x86-64 Ubuntu
24.04 and distinguishes `cuda-cross-sbsa` from the Jetson-targeted
`cuda-cross-aarch64`. Pin the 13.0 toolkit family; do not inherit the old Orin
CUDA12.6/SM87 setup. Match target GCC/glibc ABI and use a target sysroot.
[CUDA cross-platform installation](https://docs.nvidia.com/cuda/archive/13.0.3/cuda-installation-guide-linux/index.html#cuda-cross-platform-environment).

## Cross-recipe requirements derived from the source

The candidate to reproduce can be pinned at
`231b10b9780c8fb678d130a5d23676660e798add`; GGML remains
`3cf03257f219afbe7334045ff7c6a06ac68c627d`. A cross build is a new build artifact,
not automatically byte-identical to the native image or scientifically qualified.

A CMake toolchain must set `CMAKE_SYSTEM_NAME=Linux` and
`CMAKE_SYSTEM_PROCESSOR=aarch64`, cross C/C++ compilers, target library/include
search roots and the native x86 CUDA compiler's ARM64 host compiler before
`project()`. STRATA's CMake line64 defaults an unset processor to the x86 path.
Keep the exercised target flags:

```text
CMAKE_BUILD_TYPE=Release
STRATA_BUILD_DSV41=ON
STRATA_ENABLE_CUDA=ON
STRATA_BUILD_TESTS=OFF
STRATA_PORTABLE=ON
STRATA_ARM64_ARCH=armv8.2-a+dotprod+fp16+i8mm
CMAKE_CUDA_ARCHITECTURES=121-real;121-virtual
GGML_NATIVE=OFF
GGML_CPU_ARM_ARCH=armv8.2-a+dotprod+fp16+i8mm
GGML_OPENMP=OFF
STRATA_GGML_DIR=<pinned-ggml-tree>
```

`GGML_NATIVE=OFF` is material: its native ARM branch runs feature probes with
`check_cxx_source_runs`, including NEON/SVE/SME. The explicit portable ARM
architecture avoids host detection and those run probes in the inspected path.
Do not add `-march=native` on the Intel host or silently weaken the target ISA.
Other configure/build steps still need a real cross-build trial; source review
alone is not proof that the complete recipe works.

Set `CMAKE_CUDA_HOST_COMPILER` to the ARM64 cross G++ (prefer the matched GCC13
family), not Intel-native G++. NVIDIA documents `nvcc --compiler-bindir` for
cross compilation and defaults to the non-Tegra configuration when given an ARM
cross compiler. Inspect actual compiler/linker commands to ensure SBSA CUDA
headers/libraries are used. Do not pass the Tegra target-directory switch.
[NVCC cross-compilation documentation](https://docs.nvidia.com/cuda/archive/13.0.2/cuda-compiler-driver-nvcc/index.html#cross-compilation).

The current native recipe calls `ldd` on the generated ARM64 executable and
copies resolved CUDA libraries. On Intel, replace that with target-aware ELF
dependency inspection (`readelf`/cross tools and sysroot resolution); do not
execute or resolve it against the Intel host's libraries. Verify ARM64 ELF
machine/interpreter, needed libraries and symbol versions, and SM121 device
code. The final ARM64 runtime image can be assembled without running the
binary. Reserve execution/correctness tests for Spark.

For the separately requested experiment on a 16GB Windows PC, use native x86
Linux tools inside WSL2, keep source/build data on its Linux filesystem and
start at one compiler worker under a bounded memory budget. Record peak memory,
swap, compiler failure/OOM and wall time. Low parallelism is a capacity probe,
not evidence that the future larger server will be slower or faster. Do not
increase memory pressure blindly or alter the frozen Spark target to make it
fit. The parent task owns execution of that experiment.

## Current build/lab coupling that must be removed explicitly

- `spark_engine.py` rejects non-ARM64 hosts and calls `nvidia-smi` to require an
  idle GPU before a build, even though the compile container has no GPU mount.
  Make builder platform and deployment target separate validated fields.
- The shared `jobq` serializes build and GPU classes on the same host. Keep
  exclusivity on each Spark lab, but route builds to a separate host queue so
  compilation can overlap unrelated lab work. Do not let two supervisors claim
  the same GPU merely because the factory moved.
- Source paths, `FACTORY_HOME`, queue paths, process IDs, Docker IDs and cleanup
  records are currently local. A remote worker protocol needs durable request
  identity, bounded command/effect scope, completion receipts, cancellation and
  restart reconciliation. A shared SQLite file over a network mount is not a
  substitute for that protocol.
- `Manager.admit` currently records `delivery='same_host_local_image'` and checks
  the local image ID against a same-task successful build receipt. Add explicit
  remote delivery: authenticated source receipt, artifact digest, lab-side
  import/verification and task-bound admission. Reject missing/wrong images,
  target mismatch and interrupted transfers before GPU submission.
- Preserve controller ownership of task authority and Lab Manager ownership of
  hardware leases, measurement, cleanup and independent acceptance. Workflow
  orchestration remains composition of native CC contracts, not a new scheduler.

Recommended order: (1) fix stable cache paths and collect cold/warm/one-file-edit
timings; (2) qualify a real x86-to-ARM64 cross recipe against the exact candidate;
(3) implement content-addressed remote delivery/admission and restart/cancel
tests; (4) move factory/build scheduling to Intel and retain Spark-only scored
qualification. Report build-time, queue-wait and transfer-time improvements
separately. No unmeasured speedup is promised by this plan.
