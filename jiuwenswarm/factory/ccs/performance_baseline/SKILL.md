# Performance baseline integration

Inspect pinned tensor layouts, numerical paths and every demanded expert first. Use
calibrations matching the actual precision and sparsity. Ask `experiments` for a
runnable resident-slice specification and pass it to factory.engine_factory_loop
prepare_experiment, select, execute and collect under the same campaign budget.
For unsupported packed kernels, record the gap and construct a native oracle in an
owned worktree. Never silently substitute FP32 for a quantized engine ceiling.
Compare engine results only with matched workload, identity and independent checks.
Resident timings are never whole-model tokens/s. A report is not completion: record
an explicit terminal decision after collecting every active attempt.

For the native FP32 oracle, read METHOD.md's native argument and paired timing
contract. The original five arguments default to nine paired samples with batch
synchronization. To compare batch and per-operation synchronization, preserve source,
tensor, repeats and sample count, and compare paired_samples fields. The legacy
resident_matvec_s scalar remains batch timing in both modes. Retain all sample
checks and report self-check versus independent validation separately. Use
NATIVE-PROVENANCE.json to inspect the packaged source's construction lineage.


For independent numerical replay, read METHOD.md's 1.1.0 admission fields. Keep
producer self-checks separate from host recomputation. `verify_vectors` reads
bounded pinned files offline; it does not establish independent admission by itself.
The host `baseline_replay.verify_attempt` binds the same verifier to admitted task
pins and retained artifact digests. Report missing vectors as unverified, and never
use two agreeing producer vectors as an independently recomputed reference. Keep
GGUF name/type/extent validation and execution provenance explicit dependencies.
