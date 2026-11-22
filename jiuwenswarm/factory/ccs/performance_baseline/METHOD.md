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
and any failed sample makes the executable fail. Historical native executables report their own checks and maximum errors without
retained vectors; those results remain unverified by independent numerical replay.
Version 1.1.0 adds the opt-in replay path below. See the provenance
reference for the source commit and live build/GPU evidence, which are construction
evidence rather than a general performance certificate.


## Independent numerical replay (1.1.0)

No new build or GPU run has validated this source revision. Prior source/build/run
receipts remain under `NATIVE-PROVENANCE.json.historical`; they do not certify the
new binary. Five-argument calls and optional sample/cadence arguments stay valid.
To retain vectors, append both `run_id tensor_id` after explicit samples/cadence,
or supply `replay_identity` to `native_experiment`. IDs are bounded ASCII names.
The Python harness accepts the same identity in its slice specification.

The existing `/out` capture and digest-checked artifact store retain `replay.json`,
`input.f32`, `reference.f64` and `output.f32`, all little endian. Output order is the
legacy resident result followed by the last output of each paired sample. Repeated
operations and warmups are not all retained. Python retains its single resident
result (`samples=0`). Copies, vector retention and serialization are outside timed
regions; retention can affect between-sample state, so overhead remains unknown.
Bounds: 4096 rows, 262144 columns, 16777216 weights, 31 paired samples; vectors use
at most 1605632 bytes plus 16 KiB metadata. Budget sufficient `/out` capacity.

`verify_vectors` is a portable offline tool using explicit artifact digest pins.
Its expected identities are caller declarations (`admission_verified=false`). For
host admission, call `jiuwenswarm.factory.baseline_replay.verify_attempt` with the
actual child task and attempt. Before dispatch the operator must place
`baseline_numerical_replay` in task constraints, containing `run_id`, `tensor_id`,
`offset`, `shape`, `repeats`, `samples`, `synchronization`, `input_kind`,
`slice_sha256`, and `input_sha256`. FactoryLoop inherits these constraints. Native
input_kind is `calibration_mod17`; Python uses `pinned_fp32`. Pins must come from
independently inspected bytes, never copied from producer success assertions.
The host reads the admitted contract's model mount and retained digest-checked
artifacts; mutable spool files cannot supply replacement vectors. Collection must
be complete, but a failed producer numerical self-check can still be replayed.

The verifier independently multiplies the pinned binary32 weights and inputs using
binary64 products and `math.fsum` reductions. It checks every retained output with
fixed `abs(error) <= 1e-5 + 1e-5*abs(reference)`, rejects nonfinite values and shape
or identity differences, and separately compares the retained producer reference.
Neither producer reference values nor `reference_passed` choose the host oracle or
tolerance. The host reduction can differ slightly from sequential native FP64 or
PyTorch accumulation; the host criterion is authoritative for this replay scope.
Missing replay material or independent admission remains unverified.

Tensor name-to-byte-extent/type mapping remains an operator dependency; this replay
verifier does not itself parse GGUF metadata. Reuse `inspect_gguf` to establish that
mapping independently. Digest matching certifies the admitted bytes, not their
semantic interpretation. Retained vectors also cannot prove that a particular GPU
executed the computation; source/build/runtime receipts remain separate evidence.
There is no packed-expert ceiling, captured activation, whole-model acceptance or
timing verification here, and no result authorizes promotion.

Later minimum live validation, only under fresh authorization: one bounded rebuild
of this oracle plus one small FP32 calibration process with one paired sample,
followed by retained-artifact host replay on independently pinned bytes. That proves
the native retention path, not statistical timing performance. If the Python path
is to be claimed live-validated, it separately needs one bounded harness process;
CPU fixtures cannot substitute for either run. No model inference is required.
