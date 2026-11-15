# Spark correctness and speed benchmark

The first measured component is `engine.strata_verified_drafting.apply`. It uses
Strata's existing verified MTP path; it changes only `--dspark none` to `on`.
The native CC produces both immutable profile files and transformation receipts.
Static expert-cache policy, all six experts, model, image, CPU count, host reserve,
GPU allocation and other environment values are held constant. This avoids the
previous warm-draft comparison's expert-cache confound.

`factory.standard_benchmark` exposes submit/status/result. The host owns frozen
contracts, queue execution, resource limits and evidence verification. The worker
cannot select new questions, tune thresholds or promote a component. Existing
canonical-token contracts still require canonical identity; this new contract is
an explicitly different sampled task-quality test.

Public correctness data: [AI2 ARC](https://huggingface.co/datasets/allenai/ai2_arc),
ARC-Challenge, pinned revision `210d026faf9955653af8916fad021475a3f00453`, CC-BY-SA
4.0. Retain upstream card/license, raw dataset-server responses, response hashes,
revision headers and local generated cases. A deterministic hash ordering with
seed 42 selects 64 test questions without consulting their answers. The two
operational pilot questions use the train split. Normalization supports actual
four/five choice labels. Require an exact generated answer letter (optional
punctuation), stop decoding at EOS, and never extract a letter from an explanation.
This is a generation adaptation, **not** the official likelihood-based ARC score
or a full leaderboard evaluation.

Speed workload sizes follow the conventional pp512/tg128 dimensions in
[llama-bench](https://github.com/ggml-org/llama.cpp/tree/master/tools/llama-bench).
The implementation runs Strata's native protocol with an actual chat prompt,
reports native prefill and decode separately, and includes native sampling. It
is not a llama-bench execution or directly interchangeable with its pure-kernel
numbers. Each speed process receives four identical 512-token prompts requesting
128 generated tokens. Discard the first as warmup; pool tokens/time over the
remaining three. Disable prefix reuse; fail short or EOS-containing speed output.
A fresh process is not a cold SSD/cache claim. Wall time includes model startup
but the native decode metric does not.

Freeze main order ABBAABBA before observing main results. Four adjacent process
pairs provide geometric mean candidate/baseline ratios and seeded paired
bootstrap percentile intervals (20,000 resamples). Require ratio >=1.05 and
95% lower bound >1.0. Four pairs are a small sample and the bootstrap can understate
uncertainty. The correctness gate requires all answers valid, baseline >=50%,
and candidate correct-count >= baseline for every sampled question over four
runs per arm. These are observed regression gates, not population noninferiority.
Both gates must pass. Drafting must actually offer and accept tokens in measured
candidate requests. No automatic promotion/default activation follows acceptance.

Run with the existing private host Python environment:

```
python deploy/spark/prepare-benchmark.py --help
python deploy/spark/compare-benchmark.py --stage pilot
python deploy/spark/compare-benchmark.py --stage main
```

The comparison CLI uses the operator workspace root and already-produced component
receipts. It freezes sources, image and dataset hashes, creates a task, and queues
one bounded campaign; replay reconciles the existing attempt. No agent, build,
compiler or test process runs during measurements. Lightweight host queue,
recorder and independent cleanup guardian remain. Each phase gets the shared
exclusive lab lease, idle-GPU and >=108 GiB available-memory admission, 8 CPUs,
104 GiB memory/no added swap, 8 GiB host guard, and a bounded timeout. Data is
written continuously. Recovery removes only containers matching an owned nonce,
name and image. Raw wire, pipe coverage, image/boundary/final state, memory and
native request counts are independently checked after execution. Failure is
inconclusive with partial artifacts preserved.

Useful follow-up CCs are a teacher-forced score comparison (separates greedy
numerical drift from real quality loss), repeated benchmark scheduling, and a
report-to-proposal component producing a fresh single-factor contract. The latter
must not mutate frozen gates or introduce several optimizations into an ablation.

The first real comparison found a decode gain with a prefill penalty: see
[the measured results](SPARK-BENCHMARK-RESULTS.md). Reports now expose pooled native
prefill, decode and prefill-plus-decode output rates. Decode acceptance alone is
not end-to-end acceptance. Host scoring uses a byte decoder checked against every
reference vocabulary token, so it requires only the standard library; regex/BPE
encoding remains confined to preparation in the existing private environment.
