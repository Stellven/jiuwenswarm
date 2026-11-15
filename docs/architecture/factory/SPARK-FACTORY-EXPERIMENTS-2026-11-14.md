# Factory experiment notes — 2026-11-14

## Scope and implementation

Built the first bounded, durable inference-engine learning loop with GPT-6.1 Sol
subagents for loop lifecycle, hardware/source research, and profiling/prediction.
The new CCs are `factory.engine_factory_loop`, `engine.strata_prefill_chunk`,
`factory.deep_profile`, `factory.expert_prediction`, and
`factory.methodology_hypothesis`. Existing methodology,
benchmark, evidence, lifecycle and controller components remain the execution path.
Research candidates and primary sources are in
[SPARK-RESEARCH-CANDIDATES-2026-11-14.md](SPARK-RESEARCH-CANDIDATES-2026-11-14.md).

Validation before measurements: full factory suite **642 passed, 1 skipped**,
84.38 seconds; `results/factory-loop-full-tests.log` in the owned workspace.
Focused loop/controller/supervisor checks: 47 passed. Focused profile/prediction
and importer checks: 55 passed. Synthetic durability and predictor tests are
not live-agent or speed evidence.

## Native profiling failure

Task `spark-native-profile-001`, attempt `1efa6fbbbe094d35b4e1ee75b6481277`,
immutable runtime image c22e5406f9c81f5865a2318712c1f3247a86e2d1b1633a5ad19d1d3a09ffdfb4.
Enabled native DS4_PROF through the host-controlled observer mode. The engine
reached READY and prompt progress 499/512, then exited 139 without DONE or native
stage rows. The collector recorded 53 samples, no OOM events, no OOM-killed flag,
container removal and quiescence. Sampled minimum host available memory was
35,098,492,928 bytes; maximum cgroup accounting was 22,461,005,824 bytes. Unified
memory accounting and finite sampling do not exclude transient resource failures.
No stack/core was retained, so the crash cause remains unknown. Source inspection
found unchecked CUDA calls in a separate expert profiling event path as audit
targets, not a demonstrated defect. No phase bottleneck conclusion is possible.

Import initially raised KeyError on optional contract `scope`. The importer now
uses an empty limitations default; a regression test passes. The original sealed
bundle was imported without rerunning the engine and remains `measurement_failed`,
`profile_result`, `traced=true`, `scoring_eligible=false`. Evidence:
`results/profile-result.json`, `results/profile-triage.json`, and the original lab
spool directory. This is a useful recovery case, not a performance sample.

## Prefill experiment preparation

A native CC invocation produced the 512-token candidate from the 256-token baseline.
Release 68bff7025d9821f4705bb80487c40309b20ef41711c2905a8b97ba38c73bdae7.
All six experts, static cache, dspark none, model/image/data and other settings are
fixed. The benchmark checks the effective startup chunk, not merely the requested
argument. Primary speed is output tokens / (native prefill + decode seconds).
Startup, tokenization and transport are excluded. Quality uses the existing pinned
64-question ARC sample; this is a generation regression test, not an official ARC
score. Pilot uses two disjoint training examples and main uses ABBAABBA fresh-process
order, one discarded speed warmup per process, and the frozen 5% speed gate.

Review caught copied historical contract IDs before launch. The unused001 parent
and templates remain as superseded preparation evidence, with the parent stopped.
Corrected parent `spark-prefill-factory-002` and templates are under
`factory-campaign-v1/prepared-v2`, with distinct contract IDs. The operator driver
records `llm_agent=false`; it exercises the same durable CC host operations but
does not constitute a newly demonstrated autonomous Jiuwen mission.

## Remaining system work

A live expert-demand/read-readiness trace emitter must precede meaningful predictor
experiments. Offline coverage cannot predict speed without measured scheduling and
bandwidth effects. Instrumentation itself needs overhead and crash qualification.
The factory still needs bounded paper acquisition, source-changing candidate builds,
retention limits, repeated-failure circuit breakers, drift controls and reboot/long
endurance tests before a weeks-long unattended claim. See
[INFERENCE-FACTORY-LOOP.md](INFERENCE-FACTORY-LOOP.md) for the implemented boundary.

## Completed prefill comparison

Pilot `8745c353d1c142e1baa571725f5efaf2` passed operational checks; the loop
collected its evidence and submitted main `d3c362fd7cb24984b59b0977549a0277`.
All eight main cells (16 quality/speed phases) completed. The frozen verdict is
**accept**, scoped to this configuration, dataset and warmup protocol. No default
or automatic promotion occurred.

| Metric | chunk 256 | chunk512 |
|---|---:|---:|
| Native prefill input tokens/s |101.56|180.57|
| Native decode output tokens/s |14.43|14.02|
| Native prefill+decode output tokens/s |9.20|10.70|
| Sampled ARC accuracy |60/64|60/64|

There were no invalid answers or per-question regressions across the four repeats
per arm. Paired geometric mean rate ratio is 1.162735 (+16.27%), with the small-N
paired bootstrap 95% interval [1.146337, 1.179367]. Four pairs are not broad workload
qualification. Native prefill+decode excludes startup, tokenization and transport.
Generated free-text token sequences differ; the contract is a sampled quality
regression gate, not byte equality or proof of general model equivalence.

Raw timings exposed incomplete baseline warmup. The frozen analysis discards one
request and measures three. In a separately labeled post-hoc position analysis,
combined ratios B/A were 1.0102 for the discarded first request, then 1.2707, 1.1254,
and1.0918. Thus the apparent advantage decreases as the baseline warms. This does
not change the frozen gate, and the last-position comparison is not a new
acceptance test or proven steady state. A fresh predeclared longer warmup/convergence
experiment is warranted before claiming a sustained 16% improvement.
`factory-campaign-v1/prepared-v2/warmup-diagnostic.json` retains the calculation,
raw-source hashes and limitations. The complete campaign log, frozen templates,
CC receipt and source snapshots remain in the same directory.

The new proposal CC records local-evidence or paper-grounded hypotheses and can
translate a selected proposal into an unmeasured ablation design. Exact execution
still requires its ID in the admitted template policy. Export now retains the
loop ledger and policy, not only core task tables. Final validation follows below.

## Final validation and images

Final factory suite: **695 passed, 1 skipped**, 85.45 seconds. Log:
`results/factory-loop-final-tests.log`. This includes proposal-to-loop selection,
scope/budget/replay checks, offline prediction tests and read-only ledger exports.
The observer parser also refuses to name a measured bottleneck from a partial table.

Refreshed both standalone ARM64 images offline using retained dependencies:

- Agent: `factory/agent:cc-dgx-spark-factory-loop-v1`, image
  `sha256:1823984018b3b9f744e604256fc2393afe1934359fdbb5e1bb55dad1ce633447`.
- CLI: `factory/cli:cc-dgx-spark-factory-loop-v1`, image
  `sha256:2fb559d3ad5b74e6eaa3c902b023cbb2caa508a9e501a2a4b96540cf7cd081d5`.

Both sealed 20 top-level CCs; the agent image imported the actual Jiuwen facade.
No source bind was needed for these smoke checks. Old image receipts/logs remain
under `factory-campaign-v1/prior-image-evidence`. The builder and engine image were
reused: this intervention changed a native setting, not compiled engine source.
No global dependencies, driver changes, model downloads or shared image pruning.
Final source hashes/snapshot are in `factory-campaign-v1/final-source`; historical
execution/control snapshots remain under `prepared-v2`.

## Actual Jiuwen report-to-hypothesis cycle

Task `spark-factory-agent-review-001` ran the real Jiuwen facade with requested
GPT-6.1 Sol in the new standalone agent image, one turn, about 204 seconds. It read
the current/past reports, warmup diagnostic, profiler failure and research notes.
It used the native hypothesis CC, then methodology ablation, retained both outputs,
and published an evidence-citing terminal `report_inconclusive` decision. That is
the correct classification for an unexecuted design, not a failure to produce it.
It created **zero build or lab attempts** under explicit zero attempt budgets.

Its selected hypothesis is `gb10-dsv41-chunk 256-warmup-residency-v1`: at fixed
chunk 256 and dspark none, compare 1 versus 4 premeasurement warmup requests. The
agent proposed phase-aligned physical read/fault counters to distinguish file
residency from lazy initialization, a predeclared falsifier and unchanged quality/
resource obligations. It explicitly warned that four warmups would not by itself
prove convergence and that the old campaign must not be rescored. This is a real
report→new hypothesis→ablation-design cycle; it is not an executed warmup experiment.

Evidence: `results/factory-loop-agent-proof.json`, the agent session, durable
proposal/design observations and supervisor receipt. The measured pilot/main
campaign was operator-host orchestration using the loop operations. Live-agent
child selection→quiet measurement→resume across multiple new experiments still
needs a dedicated bounded qualification, followed by longer endurance tests.

All 16 main quality/speed phases have completed/exit 0/quiescent/container-removed
receipts. The sealed asset set is 256,811,098,112 bytes, including the 7,976,914,240-byte
drafting file (drafting disabled here); even the remaining inputs exceed physical
Spark RAM. This is file-backed out-of-core execution, not simultaneous full
residency. Exported parent, pilot, main, profile-failure and agent-review bundles
are indexed under `results/factory-loop-export-index.json` and individually hashed
and secret-scanned by the read-only exporter.
