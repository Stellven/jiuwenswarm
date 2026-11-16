# Ceiling methodology

Use Roofline compute, traffic and dependency lower bounds separately from empirical
calibration targets: https://docs.nersc.gov/tools/performance/roofline/ . Max of lower
bounds is a lower bound on time, not an attainable schedule. Precision and sparsity
must match. Report measured Strata end-to-end baseline, ideal expert-availability
reference, and capacity-constrained reference separately. Missing measurements stay
unknown. Account for attention/KV and compulsory selected-expert work.

Replay fixed-size pages with farthest-next-use eviction and explicit readiness.
The serial read/compute simulation is a modeled feasible reference, not proof of
global schedule optimality. No weight/expert deletion is permitted. Resident slice
checks and tolerances do not alter the independent engine-acceptance contract.
Report observer overhead as unknown until a matched observer-on/off comparison.

Capacity accounting validates positive integer KV dimensions and nonnegative integer
workspace and hardware reserved-memory bytes. Nonweight allocations exceeding usable
memory are infeasible, rather than a zero-capacity configuration. Expert retention
remains a declaration: scalar expert counts do not establish a complete tensor or
captured-routing inventory.

Ceiling inputs require explicit precision and sparsity. Phase, shape, model identity
and workload identity establish declared scope comparability; missing scope remains
a gap, and an explicit mismatch suppresses the numeric reference. Numeric terms with
missing scope are provisional arithmetic targets. This portable module cannot verify
host evidence receipts: calibration, engine and replay provenance remains unverified
even when supplied metadata claims verification. A declared hardware bound is labeled
accordingly and cannot qualify model performance by itself.

The native executable checks CPU/GPU arithmetic agreement on bytes interpreted as
FP32. Its offset/shape interface does not verify a slice digest, tensor boundaries or
GGUF format. Native experiment format is caller-declared unless separately validated
against host model metadata; existing historical measurements retain their original
evidence and scope. Version 1.0.1 changed interpretation without changing its compiled
oracle or historical evidence. Version 1.0.2 packages the agent-authored native timing
extension recorded in NATIVE-PROVENANCE.json; prior sealed packages remain unchanged.
Known packed storage layouts and validated byte extents do not establish a supported
packed native oracle, packed-kernel throughput, or numerical acceptance.

## Native paired timing

The native command accepts `weights offset rows columns repeats [samples] [batch|each]`.
The original five arguments remain valid, defaulting to nine paired samples and batch
synchronization. Samples are bounded to 1..31 and repeats to 1..1000. The existing
native_experiment helper retains its original argv and uses these defaults. A caller
may explicitly add sample count and cadence to a separately prepared experiment
within its operator envelope.

After five warmup operations and the legacy resident measurement, each paired sample
starts with device synchronization and measures the same repeated cuBLAS operation
using GPU events and a synchronized host clock. Batch waits at the end; each also
synchronizes after every operation. Outputs report `timing_schema=1`,
`synchronization`, `warmup_operations` and `paired_samples`, whose entries contain
`gpu_event_s`, `synchronized_host_s`, `maximum_absolute_error` and `reference_passed`.
Times are per operation. The legacy `resident_matvec_s` scalar always uses the
original batch timing even when synchronization is each; compare paired_samples to
study cadence. Changing cadence changes measurement boundaries and synchronization
cost, and does not establish a faster kernel.

GPU event intervals include stream idle time and enqueue gaps. Host intervals include
event recording and completion. Copies and checks occur outside those timed regions.
Samples within one process are correlated; neither a small clock gap nor nine raw
samples establishes observer overhead or statistical significance. Storage cache state
and observer overhead remain unknown. These measurements do not establish a packed
expert ceiling, an optimal schedule or whole-model tokens/s.

The original CPU FP64 accumulation and finite-output criterion remain fixed:
`abs(error) <= 1e-5 + 1e-5 * abs(reference)`. Every paired sample adds the same check,
and any failed sample makes the executable fail. The native executable reports its
own checks and maximum errors; it does not retain output/reference vectors for
independent numerical replay. Host tensor metadata and an independent reference are
still needed for stronger actual-tensor correctness claims. See the provenance
reference for the source commit and live build/GPU evidence, which are construction
evidence rather than a general performance certificate.
