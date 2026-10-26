# Public Pipeline01 standalone CPU rehearsal

`standalone_pipeline01.py` runs only staged public workloads through their unchanged
reference CLI. It is a reusable stdlib runner, not an AI4R executor. It produces
agent-authored checks and measurements; it creates no native contracts, gates,
Refs, invocation records, or governed workflow acceptance.

The coordinating subagent was GPT-6.1-Sol. Scientific subprocesses execute the
case-supplied reference implementations; they do not invoke a model or establish
provider-verified model usage. This is a workload rehearsal, not a model-generated
Builder implementation or a scored full-pipeline Codex comparison.

## Portable reproduction

The checked-in [public evidence ZIP](examples/pipeline01-standalone/standalone-results-20261026.zip)
contains both unchanged run generations and their complete public input snapshots.
Extract it to a new directory outside the checkout, then run with any supported
Python interpreter and a fresh output path:

```sh
python -m zipfile -e benchmarks/harbor_suite/examples/pipeline01-standalone/standalone-results-20261026.zip /work/pipeline01-evidence
python -B -m benchmarks.harbor_suite.standalone_pipeline01 \
  --inputs /work/pipeline01-evidence/standalone-run-02/inputs \
  --output /work/pipeline01-new-run
```

No Docker or application port is needed. On non-Windows hosts, process memory
counters are unavailable in this runner. The evidence ZIP has an adjacent SHA256
file, and each original run has its own artifact inventory. No inference account,
private grading materials or application credentials are included.

## Original invocation

From PowerShell, select a fresh output directory for every run:

```powershell
Set-Location 'D:\Codex Development Runs\jiuwenswarm-pipeline01-standalone'
& 'D:\Codex Development Runs\.harbor-pilot-runtime\venv\Scripts\python.exe' 'D:\Codex Development Runs\jiuwenswarm-pipeline01-standalone\benchmarks\harbor_suite\standalone_pipeline01.py' --inputs 'D:\Codex Development Runs\pipeline01-standalone-20261026' --output 'D:\Codex Development Runs\pipeline01-standalone-20261026\results\standalone-run-02'
```

The command above is the exact executed experiment command. For reproduction,
replace `standalone-run-02` with a new name. Existing outputs are rejected.
The initial invocation used the identical command with `standalone-run-01`;
both result namespaces are retained, including their exact runner snapshots.
Inputs must contain assignment.json, public-input-manifest.json and the public/
files listed in the manifest. No private grading material is required or read.

The runner verifies public hashes, snapshots the inputs and its own source, checks
handoff required fields, schema enums and unit agreement before experiment dispatch, and runs
variants sequentially. Each admissible variant gets three baseline/treatment
pairs in the frozen order. Both roles receive the same snapshot and repeat index.
The protocol seed 4101 fixes PYTHONHASHSEED in every child; the frozen reference
algorithm has no RNG or seed argument. Each reference process handles both
cumulative batches, with initialization and retrieval excluded from its timings.

Raw stdout/stderr and process records retain exact command argv, exit codes,
timestamps, elapsed wall time and available Windows process memory counters.
Public-data reconstruction independently checks every cumulative postings digest
and query answer. Summary operation totals determine the protocol scientific
result; invalid correctness/integrity observations abort with NOT_EVALUATED instead
of being classified as a scientific negative. Required/enum validation covers this
public handoff schema; the runner is not a general JSON Schema validator.
Actual nanosecond timings and medians are descriptive. A unit conflict
produces an attributable halt record and launches no experiment process.

The artifact inventory covers every result file except itself. Results include
the original eight public files byte for byte, assignment and manifest snapshots,
runner source, environment record, and per-variant summaries. All outputs are on D:.

Process timeouts are checked against 10 seconds and the remaining 900-second
variant budget. Windows memory counters are polled approximately every millisecond
and kill the launched process if an observed peak exceeds 256 MiB. These are
best-effort observations, not OS-enforced quotas. The specified Windows venv
executable may use a launcher; descendant-process memory is not captured by these
counters. Aggregate agent/runner memory and whole-agent wall time are not measured
or enforced. Disk usage is checked after child completion against 256 MiB; it is
not a hard disk quota. No network, provider, GPU, Docker, WSL or UI operation is
used by this runner. These restrictions are not independently OS-enforced here.

Native AI4R E1 is **NOT_RUN**. Full-task success remains **UNSCORED**, even when
the public workload scientific result is PASS. See STANDALONE-PIPELINE01-RESULTS.md.
