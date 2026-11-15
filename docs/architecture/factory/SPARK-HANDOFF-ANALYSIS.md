# Spark factory analysis and transfer handoff

## What the experiment established

The first factory draft can record an evidence-backed decision, reserve bounded
experiment capacity atomically, freeze a new child contract, submit/reconcile it
through the existing queue, retain results, and support an agent's next hypothesis.
The new CCs cover the durable loop, hypothesis proposals, native prefill tuning,
profiling analysis, and offline expert-prediction evaluation. Native ARM64 builder,
agent/control, CLI and engine images separate dependencies and runtime roles.

The measured change reused the qualified Strata binary and changed native prefill
chunk 256 to 512. It did not introduce a new kernel or beat every possible Strata
configuration. Under the frozen pp512/tg128 protocol, combined native throughput
rose from 9.20 to 10.70 output tokens/s (+16.3%). Prefill rose 101.56→180.57 input
tokens/s; decode fell 14.43→14.02 output tokens/s. Both arms answered 60/64 sampled
ARC questions correctly, with no per-question regression across four repetitions.
All 16 quality/speed phases completed and cleaned up. These are sampled generation
checks, not an official ARC score or proof of universal model equivalence.

The apparent gain depends on warmup. The baseline continues warming beyond the
single discarded request. Post-hoc ratios B/A were 1.010 on the first discarded
request, then 1.271, 1.125 and1.092. The frozen acceptance remains valid for that
specified protocol; a steady-state 16% claim is not supported. Startup, tokenization
and client transport are excluded. Four pairs provide limited uncertainty coverage.
The prior drafting trial similarly showed why decode alone is insufficient: it
improved decode but worsened combined latency. A deployment objective must be
chosen before selecting a benchmark metric.

## What the factory learned, and what remains unknown

A real GPT-6.1 Sol/Jiuwen review consumed these reports and used native CCs to
record a new hypothesis and ablation design: keep chunk 256 and all other settings
fixed, comparing one with four warmup requests. It requested physical IO/fault and
memory/placement counters to distinguish file residency from lazy initialization.
It correctly retained an unmeasured conclusion and launched zero build/lab jobs.
The measured pilot/main campaign itself was operator-host orchestrated; a new
multi-cycle autonomous agent experiment campaign has not been qualified.

Native DS4_PROF crashed with exit 139 before stage tables. The recorder preserved
partial evidence and verified cleanup; no OOM event was recorded, but there is no
stack trace proving a cause. An optional-scope importer bug was repaired and the
same failed bundle imported without rerunning the engine. This demonstrates useful
failure retention, not successful deep profiling. Fix/qualify instrumentation and
measure observer overhead before using its counters to rank engine bottlenecks.

Expert prediction is currently an offline evaluator with temporal request holdout,
frozen frequency and causal previous-token baselines. Prediction accuracy is not
speed. Real demand/readiness timestamps, traffic, wasted bytes and critical-path
waits are still needed. On shared-DRAM GB10, prefetch can add bandwidth contention
and evict useful pages; discrete-GPU paper speedups do not transfer automatically.
The research note documents MoE-Infinity, SP-MoE, Fiddler and prediction candidates
with hardware/model assumptions and falsification criteria.

## Recommended development sequence

1. Run a newly frozen warmup/convergence diagnostic; retain the old result unchanged.
2. Qualify a crash-resistant trace path with explicit dropped-event counts and
   observer-off/on controls. Capture expert demand, read completion and actual waits.
3. Compare simple predictors on whole-request temporal holdouts at equal byte
   budgets. Implement scheduling only after replay identifies a plausible gain.
4. Test one mechanism at a time, then measure the final combination directly.
   Keep separate exploration and untouched final-validation data, A/A drift checks,
   negative results, retries and crash budgets. Do not repeatedly tune the same 64
   questions until a winner appears.
5. Qualify the real agent's select→quiet→run→recover→report cycle, then progressively
   longer campaigns. Add disk retention, repeated-failure circuit breakers and
   reboot/auth-expiry recovery before attempting weeks unattended.

Final functional validation was 695 passed/1 skipped. Both refreshed standalone
images sealed 20 top-level CCs. This handoff does not rerun GPU benchmarks or claim
new performance evidence.

## Transfer contents and boundaries

The handoff directory contains a review archive and a separate Docker image
archive, SHA256 sidecars and verification receipts. The review archive includes:

- Verified task exports for parent, pilot, main, failed profile and live agent;
  previous drafting benchmark evidence; pinned public benchmark data and licenses.
- Current focused factory/CC runner/deployment source and tests, including uncommitted
  additions; base Git identity and an explicit source inventory. It is an overlay
  for the recorded full project revision, not a standalone copy of all WorkSwarm.
- Analysis, research, dependency/cleanup audit, image identities and package/toolchain
  manifests, plus a standard-library-only verifier.

No model weights, authentication profiles, raw credential-bearing mission directory,
private Python environment, shared queue state or build cache are part of the small
review archive. Images carry the retained ARM64 runtime/toolchain dependencies.
The model input identity manifest is included; the sealed asset set is 256.8 GB
(including an optional 8.0 GB drafting file). Model files must be supplied separately
for inference. The original source/model paths remain provenance, not portable
launch instructions. An exported evidence bundle is not a resumable SQLite backup.

Review and checksum verification work off-Spark with Python 3. Actual inference
requires a compatible ARM64 GB10/CUDA host and NVIDIA container runtime. Historical
contracts must not be path-edited in place: relocation needs explicit new contracts,
asset inventories and task identities. Credentials are provisioned independently.
