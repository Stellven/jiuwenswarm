# Cohesive CPU CC workflow analysis

`jiuwenswarm/factory/ccs/cc_workflow_lab` is a native capsule with four small
operations: analyze_receipts, design_workflow, benchmark_fixture and run_batch.
The batch operation has a fixed package-local allowlist and cannot dispatch
another capsule, accept shell commands or recursively batch. The process is
trusted-local; the manifest's process.exec effect launches its native worker.

The fixture projects all 24 actual CPU calls from the seven research capsule
qualification records in `research-cc-qualification-001`. It retains source JSON
SHA256, call/release identity, elapsed seconds, state and completeness. Those calls
totaled 4.135146 seconds. Per-package median invocation times were 158–182 ms.
This historical evidence does not separate interpreter or algorithm time.

## Measured CPU experiment, 2026-11-15

Final evidence directory, relative to factory workspace root:
`cc-workflow-efficiency-002/`. It contains `measurements.json`, the persistent
`ccstore/` release and fresh invocation receipts, and `host-profile.json`.
The earlier `cc-workflow-efficiency-001/` was exploratory and did not retain its
temporary store. Use round 002 as the reviewable evidence.

Selected release:
`14a8b5cf834868d1b27348cb92e54ab78f6f7ea22670518b8d07e70149889574`.

The same seven package-specific JSON receipt analyses were run as seven separate
native calls or one package-contained batch. Exact result equality was checked
on every round. Each comparator used ABBA twice, with one separate unscored
warmup for each path, fresh invocation keys, and raw durations retained.

| Comparison | Repeated prepare + seven calls median | Candidate median | Ratio |
| --- | ---: | ---: | ---: |
| Reuse already sealed release, seven calls | 1.254159 s | 1.192115 s | 1.052x |
| Reuse release, one cohesive batch | 1.241109 s | 0.170405 s | 7.283x |

These are CPU invocation overhead improvements for this tiny analysis workload,
not GPU or inference speedups. The first prepare was measured separately in an
empty store; OS caches were uncontrolled. Seven repeated role samples measured
source tree hashing at 0.402 ms median, warm prepare at 8.153 ms, direct analysis
of all seven groups at 14.3 microseconds, and native interpreter/import/JSON/analysis
at 33.133 ms. The subprocess figure combines these costs; it does not isolate
interpreter startup. Differences from the exploratory round show process-start
noise; no confidence interval or broad workload claim is asserted.

The finite bundled fixture benchmark under tracemalloc measured 5,344 Python
allocation peak bytes, worker lifetime peak RSS 31,696 KiB, and 91.0 microseconds
median over seven repetitions. Allocation tracing adds overhead. RSS includes
the interpreter and is not incremental memory. A separate instrumented Host call
measured 2,214,305 Python peak bytes; this excludes child memory. Its traced time
is not mixed into uninstrumented ABBA comparisons.

A separate warm-process cProfile call spent 0.323 of 0.443 profiled seconds in
package provenance enumeration at ccv2.py:690: 262 distributions triggered 786
metadata parses. This is profiling evidence, not an uninstrumented latency
measurement. The warmup matters: the initial cold profile additionally constructs
JSON schema validators. No host/protocol changes were made by this package.

Negative controls: replaying the same key returned the same call identity in
0.261 ms and was excluded from fresh-work comparisons. An `exec` batch operation
failed with INVALID_WORKFLOW_INPUT. Package tests reject nonfinite timing,
duplicate call identity, overlong batches/iterations and recursive/external
operation names. The initial two pytest tests and package verification passed, CPU only; the final focused suite also checks packet and batch bounds.

## Reproduce

Use the private factory interpreter and repository dependencies:

```bash
export PYTHONPATH=/home/user2/software-factory-spark-20261113/venv/lib/python3.12/site-packages:/home/user2/software-factory-spark-20261113/sources/cc-dgx-spark
/home/user2/rsi-expert-streaming-001/factory-env/bin/python tools/benchmark_cc_workflow_lab.py --output /absolute/new-evidence-directory/measurements.json
/home/user2/rsi-expert-streaming-001/factory-env/bin/python tools/profile_cc_workflow_lab.py --measurements /absolute/new-evidence-directory/measurements.json
/home/user2/rsi-expert-streaming-001/factory-env/bin/python -m pytest --no-cov -q tests/factory/test_cc_workflow_lab.py
```

The benchmark requires a new evidence directory so its first seal uses a new
store. The profiling command runs after the counterbalanced timing experiment.
Do not run CPU profiling or tests concurrently with controlled GPU experiments.
No admission certificate, model quality evidence or GPU measurement is produced.

## Optional fresh-inventory host component

`jiuwenswarm/factory/ccs/native_inventory_once` is a separate material-only
capsule containing a SHA-targeted patch, equivalence checks and an explicit CPU
benchmark. The core host source was left unchanged. The patch reads each current
distribution's METADATA once per invocation instead of three times, then emits
the same sorted Name/Version rows. It does not cache an inventory across calls.
Version changes and added/removed distributions remain visible at the next call;
fake distribution mutation/add/remove controls check that freshness explicitly.

During the root-authorized exclusive CPU slot, actual installed inventory ABBA
three times measured 90.413 ms baseline versus 32.209 ms candidate median (2.807x).
The full 262-row inventories matched exactly. Separate traced Python memory peaks
were 1,260,379 versus 1,260,639 bytes: this experiment shows no memory improvement.
An isolated copy of the actual Host using this exact patch then ran ABBA twice:
170.422 ms baseline versus 111.822 ms candidate median (1.524x). Every call checked
exact analysis outputs and complete provenance inventory equality. With no grant,
the candidate correctly returned blocked/DENIED. Both stores retain receipts.

Primary evidence: `cc-native-inventory-once-002/inventory.json`, its
`baseline-ccstore/` and `candidate-ccstore/`, and the exact copied candidate source.
The baseline source SHA256 was
`26707b7d213fce7a25dffc36ea30fd2edc1e05e1023dc5c7335cec26e45bf1fd`;
the candidate was
`87ec848e50797ff901f4c88dba54d0e2c3940f8c1d45c4b7201c5a141d036cfc`.
The first attempt `cc-native-inventory-once-001` completed its timing work but
stopped at a harness assertion that expected failed instead of the correct
blocked admission state. The harness was corrected and the entire round rerun;
only round 002 is used for these performance claims.

Four focused tests passed in 0.22 seconds using --no-cov. To reproduce the optional
component experiment after coordinating the CPU measurement slot:

```bash
/home/user2/rsi-expert-streaming-001/factory-env/bin/python jiuwenswarm/factory/ccs/native_inventory_once/benchmark.py --output /absolute/new-inventory-evidence/inventory.json
/home/user2/rsi-expert-streaming-001/factory-env/bin/python -m pytest --no-cov -q tests/factory/test_cc_workflow_lab.py tests/factory/test_native_inventory_once.py
```

The benchmark reconstructs and verifies the exact patch against the recorded base
source hash, loads a separate module copy, and never edits the production host.
These results are CPU overhead observations; they do not establish GPU, inference
kernel, quality, admission or combined batch-plus-patch performance gains.
