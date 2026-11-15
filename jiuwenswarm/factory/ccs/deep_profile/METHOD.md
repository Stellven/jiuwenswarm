# Native profile and bottleneck evidence

Call `plan`, then submit its exact `run_config: {profile: strata-native}` through
`factory.lab_client.submit` with the admitted image/build and existing Strata-v1
contract. The host alone adds `DS4_PROF=1`; replay, timeout, memory, host guard,
lease, guardian, quiet receipt, fixed argv and read-only filesystem stay under the
existing adapter. No new model dump path, Docker access or mutable contract is
accepted. Poll/cancel/recover through the existing lab tools. This requires the
same operator grants as a normal GPU lab run.

The import independently checks the actual profiled environment, derives the
profile from the sealed request and emits `profile_result` rather than
`lab_result`. It is excluded from the reference-acceptance cell set. Traced
timings and matching outputs cannot establish speedup. Run uninstrumented
comparisons after explaining an observed mechanism.

Pass retained stderr to `analyze`. The native parser consumes `ds4 prof STAGE
MILLISECONDS ms PERCENT%` prompt-stage rows, sums corresponding stages across
prompt tables and ranks them. It does not add the coarse prompt total or expert
kernel subtable a second time. Stages are summed per-device CUDA intervals, not
wall time. `experts (incl waits)` is an attribution candidate; it does not
distinguish read stalls from compute. Missing native counters remain unknown.
Each artifact is bounded to 8 MiB; each Nsight report to 10,000 rows. Separate
Nsight kernel/API/OS-runtime/memcpy durations can overlap and must not be added
into an end-to-end time budget. Nsight execution is not enabled by this mode.

`DS4_PROF` adds CUDA events, host accounting and synchronization; cost is unknown
until calibrated against an otherwise matched observer-off run. Nsight Systems
adds scheduling and tracing overhead. Nsight Compute kernel replay can serialize
work. Never feed any of these observer timings into a performance gate.

Source inspection of the retained Strata intake `src/dsv41/ds4_model.cu` found
native prompt tables, CPU-lane per-call averages and decode CUDA stage markers.
`DS4_PROF_SYNC` drains streams and is deliberately not enabled. `DS4_PRED_DUMP`
records prompt router logits/projections; it does not provide a joined decode
prediction/readiness trace. Neither aggregate profile tables nor Nsight CSV
prove predictor recall, on-time readiness, duplicate reads or wasted bytes.

For expert prediction experiments, add bounded events keyed by run/request,
phase, token, layer, expert, predictor revision and read identity. Record
prediction/enqueue/read-start/read-complete/first-demand on a shared monotonic
clock, selected experts and k, requested/completed/consumed bytes, residency at
demand and inflight joins. Include event coverage/drop counters and distinguish
critical-path demand wait from overlapping read/compute durations. Cap artifact
bytes and sample deterministically. A future instrumented build needs its own
source/image provenance and host-approved profile mode before execution.

Ordinary stream counters can also be analyzed from an already retained stderr,
without a rerun or DS4_PROF. `analyze` emits `ordinary_stream` separately from
native stage tables. The bounded parser recognizes `ds4 prompt stream, CUDA...`
rows with prompt tokens/elapsed time, streamed/file/RAM/layer-cache expert
counts, rounded file payload and reported rate, early queued/unpicked counts,
and compute read wait. Optional debug rows also expose I/O worker busy,
copy_ahead staging, DMA issue and slot wait durations. Missing counters remain
null; format drift appears as unparsed rows rather than a fabricated zero.
Every record keeps its prompt/device scope. Up to 10,000 records, 16 KiB per
recognized row and 8 MiB per artifact are allowed.

These counters overlap. In the retained uninstrumented example, a 129-token
prompt reports 2790 ms elapsed, 459 ms compute read wait and 3546 ms I/O worker
busy. The worker duration can exceed elapsed because it covers concurrent
workers; it must not be added to elapsed or interpreted as a critical path.
The reported 4.79 GB/s is file payload divided by prompt elapsed, including
page-cache reads, not measured physical disk bandwidth. Neither the rounded
3.2 GB unbuffered nor10.1 GB page-cache counters prove actual device traffic.
A compute-read-wait/elapsed ratio is descriptive within one record; it is not
a cross-device bottleneck fraction. Do not sum prompt times across devices.
Early queued/unpicked aggregates provide no joined selected-expert trace, so
recall, ready-at-demand ratio, duplicate bytes and wasted bytes remain unknown.
Use these observations to choose the next controlled experiment, with no
performance gain or observer-free causal attribution inferred by this parser.

Layer-cache counts are reported only when the native row explicitly includes
that counter; omission stays null. RAM expert counts are the engine's reported
source counts, without a cache-hit-rate inference. File/page-cache/unbuffered
payload fields likewise retain their reported source semantics, not a claim
about predictor hits, physical SSD traffic or total unique expert bytes.
