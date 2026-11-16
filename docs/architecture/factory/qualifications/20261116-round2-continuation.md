# Round 2 continuation and learning check

The operator requested a continuation of round 1 and a parallel investigation
of its work. Round 2 is a real JiuwenSwarm/Codex controller run on Spark, task
`native-throughput-goal-002`, graph `throughput-round2`, under
`/home/user2/software-factory-spark-20261113/native-throughput-round2-20261116`.

The original baseline image and frozen workload remain unchanged. The owned
source checkout starts at round 1's **unpromoted** commit
`c82131559d084d408b3a58b8e7eaaefb02477a8d`. Starting from that source does not
rebase the performance target: A remains fixed-placement source `89ae0ee612`.
The target is still at least 10% decode tokens/s gain, exact output and placement,
followed by independent unchanged-candidate ABBA confirmation.

Fresh limits: two hours, 24 controller turns, four native builds, eight comparison
jobs and 18 GPU processes. The agent must reserve one comparison and four GPU
processes for confirmation before spending the rest on screens. No candidate
promotion, remote push or evaluator modification is authorized for the agent.

## What is preserved and accessible

Round 1's stores, raw measurements, source commit and reports remain intact.
The persistent library admits 16 stores for this continuation, including both
rounds. The prior terminal decision cites `throughput-goal-final-report-v2`,
which adds advisory-helper failures to the earlier saved report. Both versions
are retained in Git; the earlier provenance JSON still describes v1 accurately.

The current library indexes record projections, not artifact bodies. To make the
actual final report reachable without inventing a new cross-task file permission,
its verified text was copied into three immutable `historical_report` observations
in round 2, each at most 4500 characters. Every page includes original task,
artifact ID, exact artifact SHA256 and offset. Those pages are searchable without
the library's string truncation. This is an explicit handoff, not evidence that
the library can already fetch arbitrary historical artifacts.

## How learning will be assessed

The agent must publish a `learning-transfer` observation before selecting work:

1. Retrieve and cite round 1 measurements, decisions, source findings and report.
2. Distinguish rejected ideas from promising but unconfirmed ideas.
3. Explain a concrete change to its intervention or budget because of that history.
4. Avoid repeating rejected settings without a stated diagnostic purpose.
5. Keep the target, baseline and judge fixed; report new measurements honestly.

We will compare actual tool calls, published decisions and measurements against
these criteria. Recall alone is insufficient. This tests adaptation through
persistent evidence, not model weight training or proof of general learning.

The parallel investigation is read-only on Spark and does not choose interventions
for the running agent. Any newly discovered evidence supplied during the run will
be explicitly recorded as external investigation input, so it cannot be mistaken
for autonomous discovery by round 2.

## Evidence of transfer before the external investigation input

Round 2 published `round2-learning-transfer` before submitting its fresh AA.
It cited round 1's three measured candidates, baseline, source-mechanisms,
followup-assessment, final decision and report pages. It explicitly rejected
blindly repeating prefetch, CPU6, inert async settings or the unchanged 200us
candidate for favorable noise. Its proposed direction was a distinct scheduling
intervention after source inspection. It reserved four GPU processes and one
comparison for confirmation. These are observed changes in the published plan,
not yet evidence of an improved experimental outcome.

The parallel review subsequently discovered existing CPU quota telemetry in the
raw round 1 evidence that the CC result had not exposed to the agent. The compact
[verified telemetry record](20261116-round1-cpu-evidence.json) was added to round 2
as `external-round1-cpu-telemetry` and announced through the controller's operator
inbox. All referenced raw hashes and the original manifest were checked again on
Spark before publication. This external input must be distinguished from the
initial plan above. No target, baseline, budget or evaluator was changed.

## Operator steering: generalization

During round 2 the operator asked which prompts/tests were selected, specifically
to avoid optimizing for one prompt shape. The current workload is operator-chosen,
not agent-chosen: two requests using the same 1471-token input and 64-token output
limit, first warming and second measuring. A/A, A/B and ABBA repeat this workload;
they do not constitute cross-workload validation.

The requirement is retained as `operator-generalization-requirement` and delivered
to the agent's operator inbox. The frozen campaign continues unchanged as a
discovery experiment. Even `target_met` would be scoped to that workload; there is
no runtime promotion or generalization claim.

Before any broader claim, independently freeze a separate holdout suite covering
code, prose, reasoning and structured content; short/medium/long inputs; short
and long outputs; and specified cold/warm conditions. Report prefill, decode,
total request latency, per-case correctness and regressions. Define the aggregate
and regression tolerances before execution, preserve every case, and do not
repeatedly tune against holdout outcomes. Match each baseline/candidate pair's
resource and cache treatment. This suite is a required next validation stage,
not something already executed or admitted by this campaign's contract.

The first round-2 screen illustrates this distinction. Its decode result was
13.9388 versus 15.1752 tokens/s (+8.87%, target not met), while retained engine
phase timings sum to 19.9987 seconds for A versus 25.1937 for B. Candidate prefill
was slower in this pair. The [verified non-scored diagnostic](20261116-round2-prefill-diagnostic.json)
records raw hashes and values. This is neither independent client latency nor a
causal regression finding: run order and cache conditions may confound it. It
was explicitly supplied as external review, not credited as the agent's discovery.

## Completed result

The real agent finished with scoped `accept`, decision 12, after nine controller
turns and about 39 minutes. Three source candidates were built and screened:

| Candidate | A tokens/s | B tokens/s | Gain | Outcome |
| --- | ---: | ---: | ---: | --- |
| Bounded caller completion wait, inherited 200us worker idle | 13.9388 | 15.1752 | 8.87% | Below target |
| Immediate ARM worker parking, original caller wait restored | 13.9255 | 14.4878 | 4.04% | Below target |
| 1ms ARM worker idle bound | 13.9121 | 15.5843 | 12.02% | Qualifying screen |
| Same 1ms candidate, separate ABBA | 14.0357 mean | 15.6148 mean | 11.25% mean | Frozen discovery target met |

Confirmation's slowest B versus fastest A gain was **10.0175%**, barely above the
10% threshold. Exact tokens/finish, fixed placement and baseline stability passed.
Independent post-run re-verification checked raw hashes, protocol boundaries and
cleanup. Twelve GPU processes, five comparisons and three builds were consumed.
The agent explicitly stopped its graph after collection: revision 19, 19 completed
nodes, status `cancelled`, no cleanup pending. No candidate promotion occurred.

The confirmed source is `231b10b9780c8fb678d130a5d23676660e798add`, image
`sha256:343355fc4ff55d899dd4247ebf8b47025bdf44c7f3431b246f36137e69eb5c59`.
The library was refreshed to 622 snapshots across 16 stores. All three source
commits, including unsuccessful interventions and their reversals, are preserved.

- [Actual final agent report](20261116-round2-agent-report.md)
- [Verified measurements, provenance and learning observations](20261116-round2-summary.json)
- [Source experiment patch series](20261116-round2-source-experiments.patch)
- [Parallel round-1 investigation](20261116-round1-investigation.md)

This is evidence of retrieval and changed decisions, followed by a better result
on the discovery workload. The initial history-based plan preceded external
telemetry delivery; subsequent mechanistic choices were assisted by that review.
It is not evidence of autonomous discovery of those counters or model training.

The confirmation's recorded prefill-plus-decode phase times averaged 19.1175s
for A and 19.2206s for B: there was no mean improvement in that sum. These are
non-scored engine phase times, not independent client latency or causal evidence.
Together with the small margin and single prompt, this reinforces the requirement
for held-out, multi-shape, correctness and latency qualification before promotion.
