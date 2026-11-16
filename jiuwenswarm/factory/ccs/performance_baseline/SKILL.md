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
