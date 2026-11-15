# CC job performance accounting for external improvement

This package measures the retained cost of invoking a job-oriented CC separately
from the shared host capability it calls. It is a descriptive, read-only input to
an external revision process. It does not score engine quality, grant effects,
choose a task, change a contract, or promote a CC.

## Identity and measurement boundaries

Native job wrappers emit `cc.job_call` when they finish, including routing errors,
API startup errors and API timeouts. `duration_ms` starts in the shared job wrapper
and ends after API result handling; it excludes Host admission, executable startup,
output validation and final Host receipt persistence. Backend `cc.call` duration
covers the existing API dispatch scope. These nested spans must remain separate.
A failed Host admission never starts the wrapper and has no `cc.job_call`; use Host
receipts to study admission failures or end-to-end Host latency.

Both events retain `invoked_capsule`, `invoked_capability`,
`invoked_capsule_version`, `invoked_release_sha256`, `backend_capability`,
`call_id` and returned `attempt_id` where available. Backend events also retain
`backend_capsule` and all previous `capsule`, `capability`, version and hash keys.
The legacy keys still identify the backend, so old consumers retain their meaning.
The wrapper passes routing context in the API subprocess environment; packet
inputs cannot select a different package, route or authority using this metadata.
This is observational context, not a signed attestation or admission credential.

The package ID comes from the wrapper's constant ID. Version and release hash are
read from the host-provided `CC_BUNDLE_DIR` sealed manifest only when its format,
package ID and enclosing SHA256 release directory agree. The hash is the CC v2
release index digest. Source/unsealed calls retain null version/hash. The wrapper
never hashes the current repository to claim it was the sealed release invoked.
Backend `release_sha256` retains its existing current-folder tree-hash meaning.
These hash schemes differ; compare package revisions using the invoked release
hash, and record the repository revision for imported shared Python host code.

The shared factory modules are imported from the installed source, outside the
sealed wrapper bundle. A package release hash alone does not freeze their behavior.
`call_id` joins wrapper and backend spans when a native Host supplies a call UUID.
A missing backend event can mean timeout, process death, routing failure or a
telemetry write failure. It must not become an assumed zero-cost backend call.

Loop execution receipts now also forward `attempt_task_id` and
`attempt_attribution: loop_child_receipt` from an explicit structured
`factory_loop.execute` result (`cycle_id`, child task, attempt ID and submitted or
collected state). The call's `task_id` remains the invoking parent. This field
only supplies observational ownership and grants no access to the child task.

## Analyze an export without running jobs

```bash
python -m jiuwenswarm.factory.cc_job_metrics \
  --events /path/to/task-export/telemetry.jsonl
# Optional complete durable attempt objects, as a JSON array:
python -m jiuwenswarm.factory.cc_job_metrics \
  --events /path/to/telemetry.jsonl --attempts /path/to/attempts.json
```

The module reads these files only. It does not open a Store, contact jobq, reconcile
attempts, build an image, or start a GPU workload. Output schema is
`factory.cc-job-metrics/1`. Supply one ordered telemetry slice from one factory
home and preserve task IDs. Replay events are excluded unless `--include-replay`
is explicit. Do not mix live and replay distributions when comparing revisions.

`packages` groups wrapper counts, outcomes and nearest-rank p50/p95/max/total
wrapper milliseconds by invoked package/version/release. Each group also contains
per-capability breakdowns. `backends` reports API distributions separately. Legacy
backend-only events remain there; alias tables cannot establish which package was
invoked. Missing/invalid durations are counted as unknown and an entirely missing
measurement has a null total, never a fabricated zero. Failure counts require the
explicit `error` outcome; other outcomes are retained as unknown.

`jobs` counts unique task/attempt identities from transitions or optional durable
attempt snapshots. `packages[].jobs` requires a successful package submit receipt
with the same task and attempt ID. Status/result polling does not assign ownership;
repeated idempotent submits do not create additional attempts. If different
packages claim the same submit, ownership is conflicting and the job remains in
`unattributed_jobs`. A loop execution with the explicit child receipt fields above
joins its job under the child task ID, with `job_attribution[].ownership` set to
`loop_child_receipt`. Other composed operations without an explicit matching
receipt remain unattributed. Older spans are not backfilled by globally unique
attempt IDs or nearby timestamps; pre-fix loop spans retain unknown ownership.
Older transitions
and results are not assigned to a CC from nearby timestamps or capability names.

Queue and run durations come from their reported transition fields, or from
explicit ordered history/start/end timestamps in an optional attempt snapshot
when the transition measurement is missing. Retry counts
require `history[].retry_of` in an optional durable attempt snapshot; repeated
calls and repeated requests do not establish a retry. Without that history,
`retries.unknown` reports the attempts whose retry status is unavailable. Snapshots
should be complete and from the same measurement boundary as the telemetry.

Build result events now include their existing `host_run.attempt_id` when present.
Only explicit task/attempt matches join build wall time and cache flags. Older or
unmatched build results increment `unlinked_build_results`. `cache_hit` currently
means base-image preparation availability, not compiler-cache hit rate. Spark
builds can leave it unknown. The cache breakdown distinguishes true, false and
unknown. Build wall time, job run time and wrapper time can overlap and have
different boundaries; they are never added into an overall cost estimate.

## Revision methodology

1. Freeze a representative job suite before editing: integration, evidence
   operations, bounded configuration qualification, inference diagnosis and
   failure/repair cases. Include failures and null measurements in the retained
   denominator. A single fast topic or successful call is not job effectiveness.
2. Save the package releases, imported-host source revision, immutable task/store
   snapshots, input identities, expected outputs, grants, runtime and workload
   distribution. Record the telemetry window and any missing completion/error
   sidecars. Calls that were never recorded are outside the report denominator.
3. Run the same offline workflow against each revision in disposable homes.
   Separate process startup and cache protocols, alternate revision order and
   retain repeated observations. Compare like-for-like capabilities and package
   versions; percentiles over tiny or mixed workloads are descriptive only.
4. Validate the job outcome independently: correct evidence, usable design,
   scope/authority preservation and a complete audit trail. Report completed
   useful jobs, failed/cancelled jobs, retries, total observed effort and unknowns.
   A faster successful API response does not establish a useful or correct job.
5. Retain counterexamples, state limitations and propose one bounded revision.
   Benchmark discovery and final holdout validation separately. Package edits
   remain candidates until independently checked; this analyzer does not supply
   promotion authority or claim causal improvement.

No GPU measurements or live-agent success is established by offline unit tests.
The test suite uses actual native Host evidence calls for routing identity and
synthetic events/fake API timeout for accounting edges. It tests task-scoped joins,
conflicting ownership, unknown retries, nested span separation and replay exclusion.

## Observed campaign feedback and next measurements

The retained `spark-broad-throughput-004` A/A campaign recorded 32 workbench
wrapper calls, 29 successful responses and three errors, totaling approximately
3.9 seconds of wrapper spans. Observed supervisor and worker intervals were about
528 and 382 seconds respectively. These overlapping measurements have different
boundaries: tool response overhead is a small visible part of the workflow, and
their difference cannot be assigned to agent reasoning, startup or idle waiting
without separate evidence. The older loop call spans lack explicit child
ownership, so the original metrics report's zero attributed jobs means unknown
attribution, not zero completed work.

The three workbench errors suggest concrete material improvements: keep
observation summaries and cited evidence IDs inside `record.values`; show the
query limit of 1 through 50 beside the example; and explain that parent evidence
scope does not grant arbitrary child-task reads. Loop collect/results are the
supported route for child evidence. Two qualification-inspection failures were
separate backend calls and must not be added to the workbench's three errors.
Only field names and sanitized failure reasons are retained in these notes.

An offline resource summary can complement the native timings after a measurement
batch finishes. The workspace helper `broad-diagnostic-v1/analyze-resources.py`
reads an explicit retained campaign proof and verifies completed spool file
hashes before extracting engine slot counts, pipe-observed first tokens, native
request timings, lifecycle CPU/throttle counters, I/O reads and sampled memory.
It runs outside the pinned runtime and does not reconcile jobs. First-token pipe
observations include buffering and startup; lifecycle CPU/I/O is not decode-only
or causal evidence. Missing GPU counters, request-level CPU/I/O and true kernel
memory peaks remain explicitly unknown. The companion workspace methodology
draft describes the proposed use; no new CC is required for this helper.
