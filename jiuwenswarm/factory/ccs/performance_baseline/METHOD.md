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
evidence and scope. No compiled oracle or historical evidence was changed for v1.0.1.
Known packed storage layouts and validated byte extents do not establish a supported
packed native oracle, packed-kernel throughput, or numerical acceptance.
