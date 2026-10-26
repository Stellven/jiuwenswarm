# Pipeline02 Codex-generated baseline — October 26, 2026

Branch: `benchmark/pipeline02-codex`, based on merged `ai4r_M1` `b983328d6`.
A GPT-6.1-Sol Codex subagent authored the standalone research worker using only
the three public files and public task. The parent reviewed it, froze its source
hash, and executed a separate host controller with real local faults. The worker
received no fault plan in its research task. No application ports, Docker, model
relay, RSI/MR source or services were used or changed.

**Scope:** common task and local fault behavior of a Codex-generated worker.
Its seven script-defined research stages are not native AI4Research capsules,
admissions, gates or model calls. Original Pipeline02 native workflow/recovery
scores and `full_task_success` remain unscored. No formal M1 result is claimed.

| Variant | Actual effect and observed result | Worker launches |
| --- | --- | ---: |
| dependency-unavailable | Controller moved the trial's real cache input after Builder. Worker exited 21, blocked before Benchmark; no Evaluation or Delivery. Original public input retained. | 1 |
| cancel-active | Cooperative file-IPC cancellation after Builder. Worker exited 20, cancelled before Benchmark; no Evaluation or Delivery. | 1 |
| observer-restart | Owned observer was actually terminated, OS exit 137. A new observer attached to the same request and original worker, which finished all seven stages, OS exit 0. | 1 |
| collection-restart | Owned collector was actually terminated after its first copy, OS exit 137. A new collector resumed the same terminal request; existing copied bytes and modification time were unchanged. | 1 |

All four scenarios passed the parent controller's common-behavior checks. Each
trial was fully collected and its owned processes exited before the next launch.
Every stage had one attempt, actual predecessor hashes matched, and original and
collected artifact hashes matched. Process creation identities prevent PID reuse;
the parent retained OS handles and read actual exit codes independently of the
worker's self-reported terminal record.

The two completed scientific runs independently reproduced all public counts:

| Trace | Two-entry LRU hits / misses | Unbounded hits / misses |
| --- | ---: | ---: |
| locality | 2 / 4 | 3 / 3 |
| scan | 0 / 6 | 2 / 4 |
| burst | 3 / 3 | 3 / 3 |

The proposed hypothesis that LRU matches unbounded misses on every trace is
refuted. Both unfavorable traces were retained. Request units,
`frozen-cache-traces-v1`, N1/N2 references and the memory/miss tradeoff were
preserved. Actual bounded CPU work performs 10,000 SHA256 rounds per cache miss
and compares computed output digests across policies. This is an authored
workload, not measured latency or evidence of an elapsed-time speedup.

## Reproduce and inspect

The [evidence ZIP](examples/pipeline02-codex/codex-results-20261026.zip) contains
the frozen controller/worker source, input snapshots, original plans, commands,
actual process identities/exits, research outputs, collection records and hashes.
Each original run folder's inventory is retained. The ZIP has a companion SHA256.

The exact host command was:

```powershell
& 'D:\Codex Development Runs\.harbor-pilot-runtime\venv\Scripts\python.exe' -B -m benchmarks.harbor_suite.standalone_pipeline02_controller --inputs 'D:\Codex Development Runs\pipeline02-codex-20261026' --plans 'D:\Codex Development Runs\pipeline02-codex-20261026\controller\frozen-plans.json' --output 'D:\Codex Development Runs\pipeline02-codex-20261026\results\controller-run-01'
```

For another machine, extract the ZIP and use the first trial's
`request/inputs/` snapshot as `--inputs`, the retained `plans.json` as `--plans`,
and a fresh absolute `--output` directory. Run from this branch's repository root
on Windows; OS process-exit collection is Windows-specific. Research input files
must remain unchanged. No account sign-in is needed for these generated programs;
the coordinating subagent model identity comes from dispatch, not workload
provider receipts. Token usage/cost and an upstream Codex CLI trajectory were
not measured, so this is not a scored comparison of native agent harnesses.

Plan snapshot outer `request_id` values were unused controller planning aliases.
The authoritative request UUID is generated once at worker launch, retained in
`request/request.json`, and joined to actual controller events and all resumed
processes. The original driver plan hashes cover the original plan objects,
which do not contain those aliases; no historical record was rewritten.

Limits: one worker at a time; 900-second cooperative worker deadline; 256 MiB
request-tree checks. No OS memory quota or hostile-code sandbox is established.
Cancellation is cooperative before stages/dispatch, not mid-computation
preemption. No native cancellation API, authenticated E1 fault-controller audit
or native scientific scoring binding was exercised. An AI4Research arm still
needs those supported bindings before the original full benchmark can be graded.
