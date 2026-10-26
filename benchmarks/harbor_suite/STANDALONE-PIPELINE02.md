# Standalone Pipeline02 Codex baseline

`standalone_pipeline02.py` is an agent-authored stdlib worker and file-IPC controller.
Its seven research records are not native CC nodes, admission contracts, governed
gates, or original Pipeline02 benchmark results. Native AI4R metrics are unscored.
No network, Docker, model-provider calls, or listening ports are used.

## Controller contract

Use the supplied Windows Python, an absolute script path, and a **new** request
directory under the isolated Codex checkout or the parent's authorized trial root.
The examples use PowerShell variables solely to shorten the commands:

```powershell
$py = 'D:\Codex Development Runs\.harbor-pilot-runtime\venv\Scripts\python.exe'
$script = 'D:\Codex Development Runs\jiuwenswarm-pipeline02-codex\benchmarks\harbor_suite\standalone_pipeline02.py'
$inputs = 'D:\Codex Development Runs\pipeline02-codex-20261026'
$req = 'D:\Codex Development Runs\jiuwenswarm-pipeline02-codex\standalone-results\trial-001'
& $py $script launch --request $req --inputs $inputs
& $py $script start-observer --request $req
& $py $script status --request $req
```

`launch` atomically claims the new directory, freezes a UUID request identity and
byte copies of only assignment, manifest, and the three public inputs, and starts
an autonomous worker. Existing directory means launch fails, with no resubmission.
The worker has an additional exclusive claim and one attempt claim per stage.
Subprocesses use `sys._base_executable` where available to avoid venv launcher PIDs.
`control/launch-ROLE-PID.json` freezes each PID, command line, creation identity,
and original request ID; each process registers `control/ROLE.json` when ready.

Wait for `control/builder-complete.json` before acting. This is an explicit
barrier: the worker cannot dispatch benchmark until the external controller runs:

```powershell
& $py $script release-benchmark --request $req
```

At that barrier, the required scientific input is the trial-local
`inputs/public/cache-traces.json`. Its exact path/hash is recorded in the builder
artifact. Moving it away or changing it before release causes a blocked terminal
result and no `control/benchmark-dispatched.json`. Frozen staged originals remain
unchanged. The worker must reopen and verify the scientific input before dispatch;
the generated `runtime/experiment.py` is also required and hash checked.

Cancellation is a durable request action checked at the barrier and before each
stage/dispatch; no benchmark is dispatched after a cancellation observed there:

```powershell
& $py $script cancel --request $req
```

To interrupt observation, wait for `control/observe.json`, then terminate exactly
that owned observer and reattach a new observer to the **same** request:

```powershell
& $py $script stop-observer --request $req
& $py $script start-observer --request $req
```

Neither observer command submits or resumes the worker. The autonomous worker
remains the original process. Stop validates creation time to prevent PID reuse;
on Windows it records the actual `GetExitCodeProcess` value after termination.
All fault-controller evidence lives under `control/`, outside research outputs.

After `terminal.json` exists, start collection. Wait for the explicit checkpoint
after the first original artifact has been copied. The controller may stop and
restart the collector while it is blocked there:

```powershell
& $py $script start-collector --request $req
# Wait for control/collection-checkpoint.json and control/collect.json.
& $py $script stop-collector --request $req
& $py $script start-collector --request $req
& $py $script release-collection --request $req
```

Restart always checks hashes of already-collected bytes and original terminal
artifacts, refusing changed bytes rather than repairing them. It copies all
original research outputs and terminal JSON byte-for-byte to `collected/`.
Completion is `control/collection-complete.json`. Without interruption, release
the checkpoint directly. Serialize observer/collector starts; the controller
does not authorize concurrent collectors. Never relaunch the worker to recover.

## Research and limits

Stages are search, screening, hypothesis, builder, benchmark, evaluation, delivery,
serially with one attempt each and no automatic repair/replanning. Every stage
hash-links its actual predecessor artifact. Inputs retain original bytes and
manifest hashes; all three public files are checked before research and dispatch.
The experiment uses N1 hit/recency rules and N2 comparisons on all three traces,
with 10,000 SHA-256 rounds per miss as deterministic real CPU work. Computed
request-value digests must match across policies. All unfavorable traces remain.

One computation-only sanity invocation (no workflow trial or fault scenario) gave:

| Trace | LRU hits/misses (requests) | Unbounded hits/misses (requests) |
|---|---:|---:|
| locality | 2 / 4 | 3 / 3 |
| scan | 0 / 6 | 2 / 4 |
| burst | 3 / 3 | 3 / 3 |

Source identity is `frozen-cache-traces-v1`; three public files, two local research
sources (trace JSON and authored notes), three traces, zero external publications.
N1/N2 are explicit references; N3's unfavorable-findings rule is respected.
Counts support a memory/miss tradeoff, with no elapsed-time speedup claim.

Worker concurrency is one; CPU only; 900-second worker deadline includes builder
handshake; 256 MiB request-tree budget checked between stages. Memory enforcement
is best effort only, with no OS memory cap. Observer and collector checkpoint waits
are externally bounded by the parent controller. Cancellation is cooperative,
not a mid-hash preemption mechanism. Controlled process termination with actual
exit-code capture is Windows-only. `terminal.worker_exit_code` is the worker's
selected return code; an independent controller should capture its OS exit code
when required. Do not equate it to external process-exit evidence.

The implementer ran only the computation sanity check. The parent subsequently
ran all four real local fault scenarios with the separate
`standalone_pipeline02_controller.py`; see [retained results](STANDALONE-PIPELINE02-RESULTS.md)
for evidence, replay commands and scope limitations. These are script-defined
standalone workflows, not native AI4Research stages or upstream Codex CLI
harness-recovery measurements. Original native benchmark scores remain unscored.
