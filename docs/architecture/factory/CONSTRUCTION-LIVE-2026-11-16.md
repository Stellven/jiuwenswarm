# Live construction acceptance, 16 November 2026

The repaired construction path completed a real agent-authored native source
change, ARM64 build, GPU execution, lost-acknowledgement recovery, evidence
collection and agent-selected follow-up. This qualifies that bounded workflow;
it does not establish a Strata throughput improvement or a whole-model ceiling.

## Authority and execution

The operator authorized four hours starting 05:39:57 UTC, ending 09:39:57 UTC
(04:39:57 Toronto), with the proposed caps retained: two native builds, four
GPU launches and twelve agent turns. Fresh campaign `construction-acceptance-v2`
used one build, two GPU launches and six turns, including the initial failed
turn. No previous campaign allowance was renewed. No remote push occurred.

The first task stopped after its shell failed to create a bubblewrap namespace
inside the control container. No build or GPU attempt occurred in that turn.
We added `factory.source_workbench` with bounded source reads/writes, stale-file
and HEAD guards, and explicit local commits. It requires the task's isolated
checkout and existing write/commit authority. It rejects Git metadata paths,
symlinks and hardlinks, and commits through Git plumbing without hooks, filters,
signing or remote operations. Host security settings were not changed.

Revision `construction-agent-v2r1` shared the original budget owner and deadline.
Its frozen runtime is commit `90d81e829dee08b06ae9f978c6247465d460d456`,
binding `3e3146379c71873f017f496e153a1febbc1f7758ab248e177e371a7295e59078`.
The original failed runtime and evidence remain unchanged. Fifty canonical
packages were sealed for the continuation; the agent used `gpt-6.1-sol`.

The agent authored commit `aa08fb790561bb6d6ea50774f7acd6c4ac90e13e`, adding
paired GPU-event and synchronized host timing to the native baseline probe.
Build `ede41bb076fe41a2b3bd686ae90e6d95` compiled and linked that source on ARM64.
The follow-up reused its admitted image without another build.

## Measurements and recovery

Both runs used the same actual FP32 tensor slice, shape 24 by 20,480, deterministic
calibration input, cuBLAS pedantic FP32 arithmetic and fixed FP64 criterion
`abs(error) <= 1e-5 + 1e-5 * abs(reference)`. Nine samples were retained per run.

| Synchronization | Median event interval / operation | Median host interval / operation |
| --- | ---: | ---: |
| Batch completion | 5.483840 microseconds | 5.530560 microseconds |
| Every operation | 10.156161 microseconds | 10.200960 microseconds |

All eighteen samples passed the probe's unchanged numerical self-check; maximum
absolute error was `2.71258656426e-7`. The agent chose the synchronization-cadence
follow-up after collecting the first run, citing its raw evidence. Host interval
increased about 1.84 times. This measures synchronization and timing boundaries,
not faster kernels. Event intervals can include enqueue gaps and stream idle time.
Samples are correlated within each process; independent process replicates and
observer overhead remain unmeasured. The legacy `resident_matvec_s` field always
uses batch timing, so compare `paired_samples` for this intervention.

The first GPU acknowledgement was withheld for 75 seconds. Recovery retained
attempt `fe2eef3d62dd4a10b32c577b643e946c` and queue job
`job-cc94f9c526ac4609a2491afe2626b3cc`, without a duplicate launch. The second
attempt was `035205c056ba43b2b96103e494a95ced`. Both completed successfully.
Quiet receipts matched inspected, stopped control containers before GPU starts.
Owned lab/control containers were removed; shared services remained running.

## Interpretation and next work

The agent ended with the prescribed `report_inconclusive` terminal decision:
construction and scoped diagnostics succeeded, but no engine promotion or
whole-model speed claim was warranted. All attempts were collected. Terminal
turn telemetry labels stream termination as `error`; retained decision/session
records show completed reporting, not a failed GPU measurement. Provider token
counts were absent, so token cost and cache savings are unknown.

The native probe still does not validate GGUF tensor metadata itself or emit
output/reference vectors for independent numerical replay. Its checks are
self-reported, backed by reviewed source and pinned build/image provenance.
Packed expert kernels, representative captured activations/routing, attention/KV
costs and matched full-engine benchmarks remain necessary for the requested
model/hardware ceiling. Four hours was an upper bound; the completed bounded
acceptance did not require spending every remaining turn or GPU launch.

Evidence lives under `/home/user2/software-factory-spark-20261113/` in
`construction-acceptance-v2` and its `construction-handoff-v2` export. The export
preserves raw measurements, task revisions, source changes, build and recovery
receipts, quiet evidence and checksums. Later packaging of the timing probe must
not be confused with the frozen runtime used during this campaign.

## Source verification and packaging

`engine.performance_baseline` v1.0.2 packages the exact agent-authored native
probe with provenance and timing guidance; it was packaged after the live run,
not retroactively substituted into that run's sealed releases. Original
five-argument calls remain compatible. `factory.engine_factory_loop` v1.2.1
corrects stale template-only methodology and tool descriptions.

The broad final regression reported 1,422 passed, one failed, one skipped and
one deselected in 167.32 seconds. The only failure was a catalog test still
expecting 49 packages rather than 50. Updating that count and rerunning the
affected test passed. The deselected existing Docker service test requires an
unavailable image. New source-workbench and baseline checks also passed their
focused runs; no additional GPU launches were used for those checks. Raw logs
are `results/construction-v2-full-tests.log` and
`results/construction-v2-catalog-retest.log`.
