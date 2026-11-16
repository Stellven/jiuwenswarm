# Construction-loop acceptance — 2026-11-16

This records the original campaign and pre-review source. Later repairs and current qualification limits are in [the construction review](CONSTRUCTION-REVIEW-2026-11-16.md).

Implementation is present; live acceptance is **partial**, not a successful
end-to-end qualification. The shared campaign used all **24 agent turns and
3 native build attempts**. It used 6 lab attempts: 2 CPU attempts, 2 GPU-class
attempts rejected before container launch, and 2 successful GPU container
launches. No budgets were renewed. No measured engine speedup is claimed.

## Implemented and verified

- Canonical migration of 48 existing declarations plus the new baseline CC:
  49 declarations pass upstream schema at commit
  `b74121c712ee5378b70ad54c4997cd81563685e7`. The mixed baseline package executes
  through both runners; all 48 historical releases verify unchanged.
- Agent-authored frozen experiments, selected sealed components, backend/runtime
  bindings, native build targets, host-side artifact admission, bounded diagnostic
  containers, raw-artifact collection and existing-queue recovery.
- Explicit terminal completion, conservative shared budgets, and remaining-resource
  follow-up proposals. Provider token/cache usage was absent in these live turns;
  monetary cost, cache savings and matched A/B efficiency improvements are unknown.
- Final broad regression: 1,359 passed, 1 skipped, 1 Docker test deselected.
  The existing Docker service test requires an unavailable pinned service image;
  actual new CPU containers, native builds and GPU probes were exercised separately.
  Export fixes received additional targeted regression checks.
- Fresh-source restoration from committed base plus exported patch/additions, and
  a CPU-only restored-runtime CC execution with no original-workspace imports.

## Live evidence and failures

The agent authored an actual-weight CPU probe with a discriminating negative
control, requested a native source build, inspected negative evidence, and chose
continuations. Two native builds succeeded. Admission initially failed because
its host Manager lacked a spool path. The repaired adapter subsequently verified
the retained binary and image without rewriting that failure. Another call
correctly rejected inconsistent host/container build normalization; preparation
now runs through the host bridge.

The third build attempt failed before compilation: queue cwd shadowed the frozen
backend. Its identity check rejected execution. Bound workers now select the
frozen PYTHONPATH and disable cwd insertion; regression tests cover shadowing.
A nested failed-build transaction was also repaired. The final native-build path
has not been rebuilt because all three attempts were spent.

The controlled lost acknowledgement yielded exactly one durable queue job,
`job-92dcb04ebc2345e7bb81dea51d6f82e6`, recovered without duplicate submission.
That job and its agent-selected continuation failed before GPU execution because
the native container guard did not accept the lab lease class. This is queue
recovery evidence, **not** successful-GPU lost-ack qualification. The guard fix
was qualified in a new frozen runtime by the two host-run probes below. Historical
bindings, receipts and failures remain intact; operator reconciliation is labeled.

## Baseline measurements

Both host-run measurements used the retained image
`sha256:af3c2bbf02b3a1273f95bebf4aa44ef5120d2ef986998a8239be1088f7def680`,
actual `blk.0.hc_attn_fn.weight` FP32 bytes (24 × 20,480), and deterministic
`x[column] = ((column % 17) - 8) / 17`. Both passed the CPU FP64 check with maximum
absolute error `2.713e-7`; both containers were removed with complete cleanup evidence.

| Repeats | Resident matvec | Empty launch | Device-copy rate |
|---|---:|---:|---:|
| 30 | 5.682 µs | 9.657 µs | 1.167 TB/s |
| 100 | 5.681 µs | 4.594 µs | 1.244 TB/s |

The small repeated copy working set can benefit from cache; these rates are not
DRAM bandwidth ceilings. Storage cache state and observer overhead are unknown.
Launch timing changes substantially with repetition count, so these two probes
do not establish a calibrated correction. They are host-run resident-slice
measurements, not successful autonomous GPU continuation, packed IQ2 expert
oracles, measured whole-model tokens/s, or independent engine acceptance.

## Export and next action

The local handoff is `construction-handoff-v1` beside this source checkout's
`sources` directory. It includes source base/patch/additions, owned source git
bundles, canonical/historical and executed CC stores, frozen runtime snapshots,
Docker archives, execution bindings, sanitized per-task evidence, raw failures,
telemetry/cost records, image verification and restoration receipts. The model
weights and credentials are not bundled. Historical absolute paths are provenance,
not permission to execute them on another machine. Relocation requires a newly
admitted binding and explicitly pinned model path; old receipts must not be edited.

**Next action is proposal-only:** a newly authorized, explicitly budgeted campaign
to qualify the repaired source-build → admitted GPU run → collected agent
continuation, including lost acknowledgement on a successful GPU job. The current
campaign has zero build and agent-turn allowance. Packed expert kernels, captured
routing/activations, matched end-to-end Strata measurements, observer calibration
and longer unattended operation remain unqualified. Changes are left uncommitted
under repository policy.
