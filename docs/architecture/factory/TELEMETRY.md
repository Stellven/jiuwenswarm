# Factory telemetry and live monitor

The stream is for external capsule improvement and operational observation. It
introduces no planner, registry, RSI controller, or automatic capsule promotion.
Only the existing factory agent chooses actions; host grants still apply.
Implementation uses the Python standard library.

## Envelope and durability

`<FACTORY_HOME>/telemetry/events.jsonl` contains UTF-8 JSON objects, one per line:

```json
{"schema":"factory.telemetry/1","event":"cc.call","ts":1794440000.0,"task_id":"factory-example","turn":3,"seq":42}
```

All events have these fields. `ts` is Unix seconds; `turn` is an integer or null
for work outside an observed controller turn. `seq` increases globally within
one home. Consumers order by `seq`, retain their last sequence, and tolerate
additional fields and event types. Timestamps can move backwards with the host
clock. A copied home starts with the sequence already present in that copy.

Writers take an exclusive `flock` on the event file, derive the next sequence
from existing lines, append one complete JSON line, flush, and `fsync` it before
unlocking. Readers take a shared lock. Files are never rotated, overwritten, or
truncated by telemetry. Capsule folder hashes are cached in each API process.
This first implementation scans the stream to allocate sequences; it favors a
single durable authority over counter sidecars and is intended for factory scale.

Evidence-derived events are emitted **after** the evidence transaction commits;
rolled-back decisions/results/transitions are not emitted. Metadata-only job
updates do not duplicate state transitions. SQLite and JSONL are not one atomic
transaction: a crash between commit and telemetry can lose a telemetry event.
Sequence order is append order, not an assertion of cross-process causality.
Native API dispatch attempts one `cc.call` for each invocation, including error
responses. Process death before completion cannot produce a completed call.

Telemetry failures never fail the caller. Each failed emission attempts a locked,
fsynced line in `telemetry/errors.jsonl` with `ts`, event name and exception class.
Count these lines to count failures. If the filesystem also rejects the sidecar,
that failure cannot be persisted. A damaged/incomplete existing event line causes
writers to fail closed and count errors rather than truncate or repair history.

Credential fields, configured secret values, and embedded credential patterns are
scrubbed using the factory redactor before persistence and again on export/HTTP.
Raw prompts, model text, output bodies, credentials, and arbitrary session chunks
are not copied into telemetry. Existing scrubbed session transcripts are separate.

## Event fields

Missing measurements are JSON null; they are never estimated as successful data.

| Event | Additional fields |
| --- | --- |
| `cc.call` | `capsule` (manifest id), `capsule_version`, `release_sha256`, qualified `capability`, `duration_ms`, `in_bytes`, `out_bytes`, `outcome`, `error_code`, `task_evidence_records`, `task_artifact_bytes`, scrubbed `inputs`, `inputs_redacted`, scrubbed `resources`, `replay` |
| `cc.material` | `tool_name` (`cc_material`/`cc_list`, optionally MCP-prefixed), `capsule`, `material`, `path`, `bytes`, `truncated`, `observed`, `bytes_scope` |
| `agent.turn` | `start` (Unix seconds), `duration_ms`, `tool_calls` (name → count), `tokens` (null or input/output token fields), `outcome` |
| `job.transition` | `attempt_id`, `kind`, `from` (null on creation), `to`, `queue_wait_s`, `run_s` |
| `decision` | `rev`, `action_type`, `evidence_id_count`, `reason_length` (Unicode characters) |
| `build.result`, `lab.result`, `evaluation` | `record_id`, `wall_s`, `cache_hit`, `ms_per_token`, `correctness`, `execution_outcome`, `engagement` (null or `{x,y}` counts) |

Call byte counts measure the API's serialized JSON packet/result (UTF-8, without
the stdout newline), before scrubbing. They are not transport framing or model
token counts. Store totals count evidence rows and sum task artifact record sizes
at completion; they are generic context, not claims of call-specific production.
Unknown capsule identities on invalid capabilities have null version/hash.
Tree SHA256 is SHA256 of sorted `relative-path + NUL + file-sha256 + LF` entries,
excluding `__pycache__` and `.pyc`, matching bundle release identity. The tree is
the capsule folder, not an attestation of imported host modules or historical
loaded bytes; host code changes must also be versioned by the external improver.

The controller sets `FACTORY_TURN`. Because the MCP process can persist across
turns, native launchers refresh the inherited value from the controller's durable
turn reservation before starting the API subprocess. Workers outside that turn
can have null or inherited turn context; job identity is authoritative for jobs.

The Codex subscription service maps `item/started`/`item/completed` tool items to
`chat.tool_call` and `chat.tool_result`, including name/arguments/result. Counts
use start events only. It maps `thread/tokenUsage/updated` → `tokenUsage.last`
input/output token fields into stream `usage.input_tokens`/`output_tokens` when
reported by the packaged Codex runtime. Telemetry retains the last observed
per-turn usage, never sums repeated cumulative reports. No usage event means
`tokens:null`; individual missing fields remain null. Cost, hidden reasoning
usage, and per-tool token allocation are not inferred. No live agent was started
to validate token availability as part of this feature.

Material reads are observed only when the stream supplies tool results. MCP
serialized content is unpacked, but arbitrary shell reads are not observed.
The current `cc_material` returns capsule/material names and text, **not the
physical file path or full original byte length**: `path` remains null and bytes
are returned UTF-8 text bytes, possibly truncated. `cc_list` is a listing, with
null material path/bytes/capsule; it is not counted as a file read. Unavailable
result detail is marked `observed:false`, not invented.

`build_wall_seconds` and `cache_hit` come from build observations; cache_hit is
currently base-image preparation cache availability, not an aggregate compiler
cache ratio. Lab wall time is null unless the result explicitly reports it;
job transition run time supplies the host interval. `ms_per_token` comes from
`details.eval_ms_per_token`; engagement uses reported boolean checks. Correctness
is usually available on `evaluation`, not the earlier lab observation.

## Operator views and export

```bash
jiuwenswarm factory telemetry TASK
jiuwenswarm factory telemetry TASK --json --since 2026-11-12T00:00:00Z
jiuwenswarm factory telemetry --home /tmp/factory-copy
jiuwenswarm factory monitor --home /tmp/factory-copy --bind 127.0.0.1 --port 8787
```

Omitting TASK summarizes all tasks. `--since` accepts Unix seconds or an ISO
timestamp and is exclusive. Tables show per-capability call count, nearest-rank
p50/p95/max duration, mean output bytes, and errors; per-turn duration, tool counts
and tokens; and transition queue/run times. The top three time spans can overlap
(e.g. a CC call inside a turn), so they are not additive CPU accounting.

Exports include the task-filtered `telemetry.jsonl`, even when empty, in
`MANIFEST.json`. Older tasks have no retrospective call/token telemetry.

The monitor polls every two seconds. `/api/tasks` returns newest-first task
summaries; `/api/story?task=TASK` returns `events` identical to story JSON plus
task/meta, engine stack, latest decision, and active jobs;
`/api/telemetry?task=TASK&since=TS` returns an event array;
`/api/job?attempt=ID` returns attempt/state and last 20 scrubbed job log lines.
It uses stable temporary SQLite copies, never initializes Store, reconciles jobs,
or writes to the viewed home. The page is self-contained, uses textContent for
record text, and supports narrow screens. Engine states derive from recorded
patch order, build/lab links and explicit decisions; missing base measurements
leave speedup blank. It does not invent per-component benchmark results when
only a combined engine was measured.

## External capsule revision and replay

An external improver creates a **new capsule version folder**, edits the capsule,
and sets its manifest version; it must not overwrite the old release. A new tree
produces a new `release_sha256`. Compare `cc.call` distributions grouped by
capsule/version/hash/capability on the **same workflow**, with equivalent store
contents, inputs, correctness contract, and cache/warmup conditions. Replay is a
cheap offline benchmark; accepting a capsule revision remains an operator/agent
decision under the normal authority boundary.

```bash
python -m jiuwenswarm.factory.replay TASK --home /tmp/factory-copy
# Preserve fresh events outside the source home:
python -m jiuwenswarm.factory.replay TASK --home /tmp/factory-copy --out /tmp/replay-results
python -m jiuwenswarm.factory.replay TASK --home /tmp/factory-copy --capability evidence.query
```

Default replay selects recorded non-replay `cc.call` events for `evidence.query`,
`evidence.read`, `builder.status/result`, `lab.status/result`, and
`inspector.inspect`. An explicit mutating/unknown capability is refused before
execution; the programmatic `calls` selection also refuses mutations. Redacted
inputs are refused. There is no arbitrary `*.status` dispatch: only installed,
known read-only implementations are eligible. Native inspector preflight/config
probes, publish, submit, cancel, and all other capabilities are refused.

The database/WAL/artifacts are copied into a disposable temporary home; credentials
and agent profiles are excluded. Status/result read the copied attempts and never
contact the queue. Inspector inspect probes a copied workspace and publishes its
fresh evidence only into the copied store. It can query Git/host/Docker metadata;
it performs no builds or lab runs. Fresh `cc.call` events carry `replay:true` and
new sequence/time/duration. Results and fresh events are printed as JSON before
temporary cleanup, or retained under `--out/telemetry/events.jsonl`.

Unchanged evidence.query/read outputs serialize byte-identically against an
identical store. This is **not historical time travel**: querying a later snapshot
may see more evidence, live jobs may have advanced since recording, inspector host
metadata may change, and inspector evidence IDs are newly allocated. Telemetry
alone cannot reconstruct historical artifact bytes, mutable attempts, or a full
workspace. Keep the corresponding workflow/store snapshot for meaningful before/
after comparisons. Replay does not run agent turns and is never a live-agent or
correctness benchmark claim.
