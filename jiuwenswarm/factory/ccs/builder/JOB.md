# Native build job

Use this package to turn a pinned, clean engine revision into an inspectable runtime image. Its submit/status/result/cancel tools and this procedure form one build job; a separate integration CC is optional for a broader source-integration task.

1. Decide whether compilation is needed. Configuration-only candidates reuse the admitted immutable runtime image. Do not rebuild merely to change a benchmark argument.
2. For Spark, use the native ARM64 builder image, pinned source and ggml dependency commits, and the existing CUDA13/SM121 flags. The worker rejects non-ARM64 hosts. Never silently emulate ARM64 on x86 or use host-installed replacements for a missing toolchain.
3. Submit once with a stable idempotency key. Preserve the returned attempt ID. The builder reuses observed successful matching task-local requests, not an arbitrary image tag. Source-changing builds require a clean committed task-owned revision under the task's existing authorization.
4. End control activity before lab measurements. Build and GPU lab share resource admission; do not run compilation during profiling. After build completion read result artifacts, immutable image ID, executable hash, toolchain identity and logs. Submission alone is not completion.
5. Diagnose failed builds by phase before retrying. A retry is a new recorded attempt; changing compiler flags is a new candidate. Inspect compile and package times separately. `build_cache_present` means a CMake directory existed, not that compilation was skipped. Verify actual work in Ninja output.
6. Hand off the runtime image identity and build receipt to the experiment. Record build wall time, phase times, configure/compile seconds, host architecture, and reuse evidence. Missing legacy fields are unknown, never zero.

## RSI evaluation

Measure time to a usable verified image, failure/retry rate, and bytes retained. Compare cold versus warm builds of the same source and toolchain separately from an incremental patch build. Keep runtime correctness and artifact identity checks fixed while optimizing build strategy. Do not spend GPU experiments measuring a CPU build-cache improvement.

The current cache key includes source identity: safe exact-revision reuse is implemented; efficient cross-revision incremental compilation remains a lead, not an achieved speedup. This revision adds measurement and native-host enforcement, not a claimed compile-time improvement.

Spark llama.cpp target: set build_target to llama-server, and dependency to the same pinned clean source checkout (embedded ggml). This selects LLAMA/ GGML CUDA13 flags and build/bin/llama-server; the runtime entrypoint is /opt/llamacpp/llama-server. No model access or network is permitted during compilation. Strata defaults remain unchanged.

For a Spark llama-server image startup proof, submit with `target: spark-gb10`, `build_target: llama-server`,
`delivery: image` and `verify_image: true` in the request. Use the build node ID and a stable idempotency key.
The same job records the source revision in the executable, runs `/opt/llamacpp/llama-server --version`
inside the immutable image with networking and GPU devices disabled, and compares the in-image SHA-256
with the compiled binary. It supplies the host CUDA driver library read-only for dynamic linking.
Use `result` after success and cite `<attempt_id>:image-check` for the startup proof and
`<attempt_id>:receipt` for the image identity. The image check records `executable_sha256` for lab
`expect_sha256`.
