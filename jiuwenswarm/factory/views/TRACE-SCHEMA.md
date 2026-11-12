# Expert trace contract: `expert_trace/2`

This is the engine/view handoff, not a claim that the engine emits these fields
today. The view consumes JSONL in this format and the current selection CSV.
Its normalized, embedded/downloadable document is `expert_activity/1`.
Views run offline, outside the inference timing window, and make no engine calls.

## Wire format

UTF-8 JSONL: a `meta` record followed by `expert` and optional `token` records.
Every record has `schema: "expert_trace/2"` and a string `run_id`. Appended runs
must have different run IDs. The expert key is `(run_id, phase, token_idx, layer)`;
one record per key, at the **first** expert consumer, not one per expert matmul.
IDs and layer/token indices are zero based. Expert IDs refer to the real router,
never a simulated predictor. Eight selected IDs are expected for Qwen3.6-A3B;
other models declare their count in metadata. Predictions may have K other than 8.

Missing, unsupported, unmeasured, or not yet finalized values are JSON `null` or
omitted. They normalize to `null` and render as **UNKNOWN**, never zero. An empty
predicted list means the producer observed no prediction; a null list means it
does not know. Zero bytes is valid only after the corresponding counter ran.

```json
{"schema":"expert_trace/2","type":"meta","run_id":"run-1","origin":"real","image_id":null,"n_layers":40,"n_expert_used":8,"phase_definition":"workload","sampling":{"mode":"all","stride":1,"expected_tokens":{"prompt":195,"decode":63}},"overhead":{"mode":"trace; operator A/B required","measured_ratio":null,"evidence_id":null}}
{"schema":"expert_trace/2","type":"expert","run_id":"run-1","phase":"decode","token_idx":195,"layer":1,"selected_ids":[1,2,3,4,5,6,7,8],"predicted_ids":[1,2,3,4,9,10,11,12],"prediction_source":{"kind":"pregate","source_layer":0,"distance":1},"readiness":[{"expert_id":1,"class":"prefetched_done","required_bytes":1921024,"resident_bytes":1921024},{"expert_id":2,"class":"inflight"},{"expert_id":3,"class":"resident"},{"expert_id":4,"class":"queued"},{"expert_id":5,"class":"missing"},{"expert_id":6,"class":null},{"expert_id":7,"class":null},{"expert_id":8,"class":null}],"demand_read_bytes":4096,"demand_wait_ns":1200000,"speculative":{"issued_bytes":8192,"read_bytes":8192,"used_bytes":4096,"wasted_bytes":4096,"timely_bytes":4096,"late_bytes":0,"unused_scope":"target_arrival"},"arrival_ns":5500000000,"fill_end_ns":5501200000}
{"schema":"expert_trace/2","type":"token","run_id":"run-1","phase":"decode","token_idx":195,"start_ns":5490000000,"end_ns":5509000000}
```

The example is synthetic documentation, not run evidence. `meta` may additionally
carry `effective_config_line`, `image_ref`, and `phase_summary` with load/prompt/
decode `duration_ns`, `tokens`, `demand_read_bytes`, `demand_wait_ns`. Load has no
token/expert routing records; report load counters separately in `phase_summary`.
`sampling.mode` is `all`, `stride`, or `unknown`; specify any layer filtering and
truncation. Expected counts are counts, not token-index bounds. Token indices can
continue from prompt into decode and must not be renumbered by the converter.

## Readiness and timing semantics

`readiness` has one entry per selected ID, across **all** its expert tensors/files.
Capture at arrival, before demand fill and before cancellation changes the queue.

| Class | Meaning |
|---|---|
| `resident` | All required pages are present at arrival; no completed speculative read is established as their source. Includes prediction-time resident pages. |
| `prefetched_done` | All required pages are rechecked resident at arrival and matching speculative reads completed before arrival. This is an operational attribution, not proof that prefetch caused residency. |
| `inflight` | Required bytes are not all resident and a matching speculative read is running. Late; demand may join it or read missing bytes. |
| `queued` | Required bytes are not all resident, no matching read is running, and matching work is queued/not started. Late; demand normally takes over. |
| `missing` | Required bytes are not all resident and no usable speculative work covers them. Demand read is required. |
| `null` | No valid arrival measurement. |

Resident-at-arrival takes precedence over queue state. Mixed tensor/chunk states
collapse to the worst unready state (inflight, then queued, then missing only if
no usable work), with `required_bytes`/`resident_bytes` preserving partial coverage.
For ambiguous mixes producers may emit null rather than claim readiness.
`pred_done`/`hit_done` in old stats only mean worker completion, **not** this
`prefetched_done` class: pages can be evicted, or skipped by a worker's mincore.

`arrival_ns` and `fill_end_ns` use a single monotonic nanosecond clock within a
run; record the clock and epoch in metadata if comparing streams. `demand_wait_ns`
is main-thread wall time inside the blocking demand-fill scope, including job
setup, residency probes, joins and read waits; it is not expert compute time.
Fill end minus arrival is not silently substituted for this scoped timer.
`token.start_ns`/`end_ns` bound actual token execution, not layer callbacks. A
producer may supply `duration_ns` instead. Optional token `demand_wait_ns` is the
complete, serial main-thread sum. Otherwise the view sums layer waits only when
all declared layers are present and measured. Partial sums remain labelled partial.
Rest-of-token = duration minus complete demand wait is **inferred residual wall
time**, not CPU compute, GPU compute, page-fault time, or exclusive kernel time.

## Bytes and speculative accounting

All byte fields are integer bytes, not sectors, KiB or device block traffic.
Demand bytes count bytes actually returned by demand `pread`, including duplicate
reads; joins are not demand-read bytes. `join_waits`, `join_wait_ns`, `join_bytes`
may be added to expert records. The latter two are already aggregate engine stats.
Do not add join time to demand wait again: it is a subset of that wait.

Speculative fields are attributed to this **target** layer/token, once per actual
submission/chunk, even for multiple predictor distances. `issued_bytes` is queued
request volume, `read_bytes` actual pread bytes, `used_bytes` actual speculative
read bytes covering selected IDs, and `wasted_bytes` actual bytes for IDs not
selected. Cancelled request bytes are not wasted reads. `timely_bytes` is the used
read volume completed before arrival and `late_bytes` is used read volume that
completed later. Finalize after workers drain; incomplete fields stay null.
Use range ownership to avoid double counting overlapping predictions and page
boundaries. Do not derive waste from recall × bytes or from total minus demand.

`unused_scope: "target_arrival"` means unused for the target routing decision.
Those bytes may be reused by a later token. Claiming **never used in the run**
requires `unused_scope: "end_of_run"`, tracking subsequent accesses/eviction and
retiring outstanding predictions on reset/exit. Patch 10's
`decode_wasted_async_bytes` measures target-arrival misses, not lifetime nonuse.
No view labels that counter as lifetime waste.

## What the callback already knows; what must be added

Basis: `expert-streaming-sourcemap.md` sections 4–8, patches
`10-expert-readiness.patch` and `11-inflight-join.patch` in `xs-dev`, and the
selection callback in `opt-artifacts/12-selection-trace.patch` (also inspected
while applied in `llama-opt`). The working checkout changes concurrently; the
final P12 format/coverage notes are in `opt-artifacts/F16-design.md`.
Source inspection is not a live-run verification.

| Needed field | Available now | Engine work needed for v2 |
|---|---|---|
| Selected IDs, layer | Host I32 `src[2]`, shape `[n_used,n_tokens]`, valid before first CPU MUL_MAT_ID | Preserve IDs **per token**, not the ubatch union; suppress repeated diagnostic callbacks. |
| Phase/token | CSV tracks cumulative token index; engine calls `n_tokens==1` decode | Carry true workload phase. A one-token prompt is currently classified decode; declare `phase_definition: "ubatch_size"` until fixed. |
| Predicted IDs/source | Prediction batches, source distance, target layer in pregate state | Serialize at arrival before clearing/cancelling; retain each distance/source and deduplicate union for recall. Current CSV emits distance-1 IDs. |
| Selected arrival readiness | Async batch snapshots; patch 10 mincore readiness bytes split predicted/unpredicted | Retain per-ID, all-tensor residency and batch state **before** cancellation/joins. Recheck completed prefetch at arrival; completion alone is insufficient. |
| Demand bytes/wait | `fill()` returns sync bytes; `Counters` includes total and phase wall ns | Capture per-layer deltas across files around fill; retain token identity; do not use teardown totals for individual cells. |
| Spec issued/read/used/wasted | Async batch byte counters; patch 10 marks non-hit batches and counts eventual bytes | Persist batch-to-target ownership, source/distance, final read counts, timed completion; deduplicate overlaps; retain non-hit predictions at reset/exit. Track future use for lifetime waste. |
| Arrival/fill end | Callback and blocking fill boundaries exist | Record steady-clock ns at both; token start/end separately. No extra graph cuts needed. |
| Join waits/bytes | Patch 11 counts joins and blocking join ns in filler | Serialize layer deltas; aggregate join bytes can include overlap with multiple chunks. |
| Execution placement | `-cmoe` buffer override, GPU offload logs, host callback | Optional actual backend per node for direct attribution. Current view labels placement from argv/logs as inferred; page-cache residency does not move experts to GPU. |

## Current CSV conversion and normalized view

The preserved engine patch `xs-dev/opt-artifacts/12-selection-trace.patch` emits:

```csv
run,token_idx,layer,phase,selected,predicted
123456789,195,0,decode,1 2 3 4 5 6 7 8,
```

`run` is an opaque session ID, not a nanosecond timestamp. The converter accepts
this format, CSV with just selected IDs, and v2 JSONL. It preserves appended-run
boundaries and absolute token indices. P12 indices count processed ubatch tokens,
including CLI warmup; they are not sequence positions or a promise that all
records are scored decode tokens. Output-pruned prompt rows may be absent at
later MoE layers; surviving rows retain noncontiguous output-mask token indices.
Missing cells stay UNKNOWN. Missing predicted **column** means UNKNOWN;
an empty present column means an empty prediction. CSV readiness, timings and
bytes stay null. No trace yields an UNKNOWN map; no synthetic cells are generated.
Unknown phases, malformed/duplicate rows and missing records are declared in
coverage notes. `--trace-run` can select one appended session; aggregate stats
are not apportioned across appended sessions.

`expert_activity/1` contains `provenance` (run/task/image/config, sources with
SHA256 and per-source overhead, phase coverage and sampling), `stats` (raw
subsystem snapshots), `phases`, `activity.events`, `predictions`, `timeline`,
`changes`, and `notes`. It keeps raw ns/bytes; HTML uses ns/µs/ms and
bytes/KiB/MiB/GiB (powers of 1024),
with exact values in cell details. Recall = set-intersection / selected count on
records where prediction was observed; coverage/denominator accompany each row.
No teardown mean is spread into per-token observations.

Factory changes are read through `Store` APIs on a stable temporary DB/WAL copy;
the original factory home is never opened by `Store.__init__` or written. Change
links use explicit component/attempt/image/evidence references. A nearby record
in time is insufficient to establish causality. Unlinked fields remain UNKNOWN.

## Overhead and operation

Every source declares `overhead: {mode, measured_ratio, evidence_id}`. Stats-line
emission is declared negligible, not an A/B measurement. Readiness probes, DIAG,
traces and external thread sampling are separate instrumentation costs. Trace
`measured_ratio` is **instrumented wall time / uninstrumented wall time**, from
operator A/B with a reference `evidence_id`; null until measured. Thread sampler
self CPU percentage is not this ratio. Never reuse performance speedup ratios
as instrumentation-overhead ratios. DIAG timing is explicitly perturbed.

```sh
python -m jiuwenswarm.factory.views /path/to/run --out view.html
python -m jiuwenswarm.factory.views /path/to/run --trace trace.csv --out view.html
python -m jiuwenswarm.factory.views TASK --home /path/to/factory --out view.html
```

Optional `view-meta.json` in a run directory supplies run/image IDs, trace sampling,
and `overhead` (a trace overhead object) when the wire CSV cannot. Trace paths are
explicit (`--trace`) or discovered inside the run directory; no container path is
followed into an operator home. The CLI defaults to **replay / offline snapshot**;
`--mode live` labels an explicitly requested live-evidence snapshot, with no polling.
Synthetic metadata always retains the synthetic label. `--json-out` also writes
the normalized document. The self-contained HTML embeds that document and offers
an offline JSON download. The sample is recorded J-OM13 aggregate evidence, not a
new engine run or a live-agent result.
