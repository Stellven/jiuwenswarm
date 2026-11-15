# Verified drafting comparison on the oversized Strata model

The CC improves warm native decode, but it does **not** improve the complete
512-input / 128-output native request. Keep these conclusions separate.

| Metric | A: no drafting | B: verified drafting |
|---|---:|---:|
| Pooled measured decode output tokens/s | 14.5041 | 16.9632 |
| Pooled measured prefill input tokens/s | 106.8882 | 73.0889 |
| Output tokens/s including native prefill + decode | 9.4013 | 8.7967 |
| ARC sample correct per run | 60/64 | 60/64 |
| Invalid answers | 0 | 0 |

The predeclared decode comparison passed: paired geometric mean B/A **1.16954**,
95% paired-bootstrap interval **[1.16536, 1.17373]** over four fresh process pairs.
This is a **16.95% decode gain**. Including native prefill makes this short-output
workload **6.43% slower** with drafting. These native rates exclude model loading,
tokenization and client overhead. The combined rate was added as a descriptive
postrun metric; it was not substituted into the frozen decode acceptance gate.
Future benchmark reports include it automatically and explicitly label acceptance
`warm_native_decode_only`. No default was changed or component promoted.

All eight runs scored 60/64 (93.75%). Every adjacent A/B pair produced identical
quality token sequences on all 64 questions. No per-question accuracy regression
was observed. All free-generation speed sequences differed between A and B, so
this result does not establish exact greedy equivalence on arbitrary continuations.
The older canonical-token contract remains separate and was not relaxed.
Four repeats of the same 64 questions are not 256 independent quality questions.

The public correctness source is [AI2 ARC-Challenge](https://huggingface.co/datasets/allenai/ai2_arc),
pinned to `210d026faf9955653af8916fad021475a3f00453`, licensed CC-BY-SA 4.0. This is
an exact-answer generation adaptation of a deterministic 64-question test subset,
not official likelihood/acc_norm or a full ARC score. The speed workload uses
512/128 dimensions inspired by [llama-bench](https://github.com/ggml-org/llama.cpp/tree/master/tools/llama-bench),
with an actual chat prompt and Strata sampling; it is not a literal llama-bench run.
See [the methodology](SPARK-STANDARD-BENCHMARK.md) for selection and scoring rules.

## Experiment and identities

- Component: `engine.strata_verified_drafting.apply`, sealed release
  `b930681c6bd7567462db358ec1fee28546a769f250ebf93d6c182b6790229c90`.
  Actual native CC calls produced both A/B profiles and receipts before testing.
- Only the drafting feature changes: profile `--dspark none/on` and corresponding
  native request `spec=0/1`. Confidence 0.65 and static expert-cache settings are
  common to both. All six target experts stay enabled.
- Same immutable Strata image in every phase:
  `sha256:c22e5406f9c81f5865a2318712c1f3247a86e2d1b1633a5ad19d1d3a09ffdfb4`.
  Native source revision: `ffa80d73133ea5c548aefe57889a16e8085a938f`.
  No engine rebuild, model download, driver change or global package installation.
- Dataset SHA256: `f4752d3baf81c2262ede5000ec18e4d5e0db21b3c7386c85618ba25adf1164a3`.
- Main contract SHA256: `80156e424ede236ff5c64652dbb2a9e1d7602298c6e050d24ec160ebe381f596`.
- Pilot attempt: `fd7218c7978447d1afeb18eb0ab48661`; two disjoint train questions,
  warmup plus one measured speed request per arm. Operational verdict `pilot_ok`.
  Its 14.38/16.73 tokens/s was preliminary, not the accepted comparison.
- Main attempt: `5de53283dd8e4dfc928a9094f124faa1`, task
  `spark-arc-drafting-main-001`, order **ABBAABBA**. Eight quality processes plus
  eight separate speed processes. Per speed process: one discarded warmup and
  three measured requests, each 512 input / 128 output tokens, no prefix reuse,
  no EOS. Twelve measured speed requests / 1,536 output tokens per arm.
- Main campaign wall time: **2,613.90 s (43.57 min)**. Each process: 8 CPUs,
  104 GiB cgroup memory / no additional swap, idle-GPU and >=108 GiB available-RAM
  admission, 8 GiB host guard. Lowest sampled host availability: **31.52 GiB**.
- All 16 main phases exited zero, retained complete evidence, became quiescent
  and removed their owned containers. The shared queue worker remained; unrelated
  services were not stopped. No builds/tests/agent turns ran during measurement.

| Cell | Arm | Measured decode tokens/s |
|---|---|---:|
| 1 | A | 14.5573 |
| 2 | B | 16.9462 |
| 3 | B | 16.9398 |
| 4 | A | 14.5204 |
| 5 | A | 14.4735 |
| 6 | B | 16.9899 |
| 7 | B | 16.9768 |
| 8 | A | 14.4657 |

The candidate accepted 696 of 840 offered draft tokens across measured requests.
First-request decode rates were lower (A 8.78–9.71, B 7.61–8.41); warmup exclusion
matters. Fresh process initialization is not proof of a cold storage cache.
Four process pairs are a small sample; the bootstrap may understate uncertainty.
No matched published result for this exact pack/configuration is claimed.

## Retained evidence

Workspace: `/home/user2/software-factory-spark-20261113`.

- `benchmarks/component-apply-001/`: actual component calls, sealed receipts and
  immutable input/output profiles.
- `benchmark-data/arc-v1/`: frozen cases plus raw public source pages, revision
  headers, response hashes and dataset card/license.
- `benchmarks/arc-drafting-main-001/{contract,result,summary}.json`: frozen contract,
  original host-verified verdict and metrics.
- `benchmarks/arc-drafting-main-001/execution-source/`: all six execution modules
  matching the original predeclared SHA256 values, retained before later API and
  reporting improvements. The original report is not rewritten.
- `mission-store/benchmark-spool/5de53283dd8e4dfc928a9094f124faa1/`: raw native
  stdin/stdout/stderr, pipe coverage, host/cgroup/process samples, exact image and
  boundary inspections, recovery intents, phase reports and campaign manifest.
  Evidence is also imported into the task's durable artifact store.
- `benchmarks/arc-drafting-main-001/stdlib-independent-reanalysis.json`: original
  report reproduced exactly with the dependency-free decoder before adding
  secondary metrics. `decoder-equivalence.json` checks all 129,280 vocabulary
  token byte strings against Strata's reference decoder and all 70 prompt roundtrips.
- `secondary-metrics-reanalysis.json`: independent reanalysis with explicit
  prefill/combined metrics; original quality, gates and bootstrap are unchanged.
- `benchmarks/standard-cc-proof-001/`: actual containerized native CC status/result
  calls through a finite host bridge; both succeeded reading the real campaign.

## Attempts, gaps and next input

The original warm drafting observation also changed expert caching, so it could
not establish causality. The new profile-transform CC makes the feature change
reviewable, and the frozen comparison prevents in-run threshold or question edits.
The pilot qualified protocol framing and answer extraction on training questions
before test questions were measured. No failed GPU attempt or selected retry is
hidden in the accepted main comparison.

A dependency review found host answer scoring unnecessarily imported encoding's
`regex` dependency. Scoring now uses only the reference byte-decoding operation,
validates the frozen tokenizer inputs and needs no new host packages. Preparation
still uses the existing private environment's native encoder. Another integration
gap was a container `/factory` Python path being passed to a host worker; the
submitter now sends the operator workspace's host source path. Regression tests
cover scope, input pins, raw protocol corruption, incomplete evidence, source drift,
quality regressions, insufficient speed confidence and a decode gain accompanied
by an overall slowdown.

Test harness attempts are retained: initial collection inherited unavailable
coverage addopts, then a run used executable fixtures on a `noexec` `/tmp`; the
full suite also exposed missing donor-gate configuration and a catalog expectation
that omitted the two new CCs. The final commands disable unrelated coverage/cache
plugins, place executable fixtures in the owned workspace and explicitly configure
the existing read-only donor lab path. These harness issues did not occur during
GPU measurement and do not alter its evidence.

The next useful input is **not** “enable drafting globally.” Request a fresh
single-factor workload-length experiment: hold this component and correctness
sample fixed, vary generated length in separately frozen cases (128/512/1024),
and report prefill, decode and combined latency. The measured warm rates suggest
an amortization crossover around 222 generated tokens for this one 512-token
prompt if rates stayed constant; that is a hypothesis, not a measured threshold.
The worker's v1 128-token limits must be versioned rather than silently changed.
A teacher-forced scoring/equivalence CC would help investigate why free-generation
outputs differ. A report-to-proposal methodology CC should carry these findings,
limitations and a fresh input contract forward without changing the old verdict.

## Factory validation and report-to-input cycle

Final factory regression: **574 passed, 1 skipped**, including the new negative
case where decode improves but combined native latency regresses. Updated standalone
images were built only after GPU profiling ended:

- Agent: `factory/agent:cc-dgx-spark-benchmark-v1`, immutable ID
  `sha256:adfccdb5ada8789e9d8144a4a9d77273858f46fde4fb726703f25d205ada6a2f`.
- CLI: `factory/cli:cc-dgx-spark-benchmark-v1`, immutable ID
  `sha256:5a8be1212701a0ad0866c5a549568728b2dfb09cbb4a85ca2dc5660aa3fcceec`.

Both sealed 15 top-level CCs without a source bind. The agent imports the actual
JiuwenSwarm facade and uses the retained native dependency closure. An initial
CLI Dockerfile rebuild tried to reinstall an unchanged dependency under disabled
networking and failed; the successful offline refresh explicitly reused the
existing immutable CLI dependency image, copied only current source, and retained
a closure manifest. No network/package installation or host changes were needed.
Build contexts and failed/successful logs remain in the operator workspace.

The actual `factory.methodology_followup.followup` CC was then called inside the
new standalone agent image, with only the evidence store mounted. It consumed
normalized, already-verified measurements plus the secondary-metrics observation,
and emitted a **proposal-only** draft-cost experiment with evidence references,
unchanged grants/contracts and no submission. The original native receipt is
`native-methodology-followup.json`. This exercise found a real methodology gap:
the existing CC selects a sensible draft-cost inspection, but does not itself
turn the new report's prefill penalty into a concrete workload-length contract.
`reviewed-next-input-proposal.json` retains that additional human analysis as a
separate, unapproved proposal. No second optimization or longer GPU experiment
was started. This gives the next report-to-input CC a concrete test case.
