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
