# Round 1 investigation

Requested by the operator while round 2 runs. This investigation read retained
source, decisions, tool-call records and raw measurement files; it did not run
additional GPU work or alter the round-1 store. The scope is task
`native-throughput-goal-001` and source commit
`c82131559d084d408b3a58b8e7eaaefb02477a8d`.

## Finding

Round 1 demonstrated real evidence-driven execution, but not a confirmed 10%
speedup. Its useful lead is stronger than the agent report explains: existing
telemetry shows quota throttling during the baseline's measured decode and none
in the candidate. The main integration gap is exposing retained diagnostic
evidence to the agent, rather than collecting another measurement immediately.

## What the agent actually did

The store's `history-summary` cites two older decisions with database, task,
record and snapshot hashes. It correctly distinguished the earlier CPU4 loss
from a clean causal experiment because the historical placement and A/A were
confounded. Decision 1 requested fresh A/A; decision 2 explicitly avoided
blindly repeating CPU4. Decisions 3 and 4 selected prefetch and CPU6, then
decision 5 changed direction to retaining compute parallelism while reducing
idle spinning. Decisions 6 and 7 edited, built and measured that source change.
Decision 8 reported the target as unconfirmed and stopped further work.

This is observable use of retrieved history and in-run evidence. It is not
proof of model training, durable internal learning, or consistent cross-campaign
adaptation. Round 2 must demonstrate retrieval and changed choices again.

The graph reached revision 18 with 18 completed leaves. Many leaves were source
inspection/read operations; this is not 18 optimization trials. The record
shows sequential evidence-backed appends, including correction of a missing
per-append definition. It does not establish a complex branching or parallel
multiworkflow search. Literal inputs leave the current diagram without
data-flow edges; revision citations retain causal sequencing.

## Source change and plausible mechanism

The clean source diff changes only CPU-lane Pool construction in
`src/dsv41/ds4_model.cu:6886`: ARM64 idle spinning becomes 200us instead of 20ms.
The worker count, generation tickets, atomic ordering and condition-variable
wakeup code remain unchanged. In `src/dsv41/ds4_pool.hpp`, `cpu_relax()` has
x86 implementations but no ARM64 instruction; the idle loop repeatedly checks
atomics and the clock until the timeout. Shortening this interval plausibly
reduces quota consumption by idle workers and leaves capacity for launch/IO.
This is a scheduling intervention, not a changed measurement timer or kernel.

The patch applies to all ARM64 deployments using this source path, despite
being tested only on Spark with an eight-CPU quota and this workload. More
frequent sleeping may increase wake latency on other workloads. The native
build disabled STRATA's unit suite; exact token matching on this request is
scoped validation, not concurrency stress or cross-platform qualification.

## Previously unreported diagnostic evidence

The report's statement that CPU/quota counters were not collected is too broad.
`samples.jsonl` already records cgroup `cpu_stat`; `pipe-events.jsonl` maps stdout
bytes to host monotonic timestamps. Eight source files were checked against the
sealed comparison manifest. The reproducible calculation and raw hashes are in
[the small CPU evidence record](20261116-round1-cpu-evidence.json).

For the idle-spin screen, samples inside the second request's first-token-to-DONE
receipt window show:

| Retained sampled interval | Baseline A | Candidate B |
| --- | ---: | ---: |
| Interior elapsed seconds | 4.236 | 3.207 |
| CPU seconds consumed | 33.843 | 14.895 |
| Quota periods throttled / observed | 43 / 43 | 0 / 32 |
| Cgroup throttled counter increment, seconds | 4.159 | 0 |

These are unequal interior windows from approximately one-second sampling,
excluding boundary gaps. Pipe receipt timestamps are not exact kernel phase
boundaries. The cgroup throttled counter is not directly lost wall time and must
not be converted into a percent stall by dividing by elapsed time. Whole-process
counters likewise show 84 throttled periods for A and zero for B, but include
loading and prefill. The observations support the contention hypothesis without
proving that it explains the entire 9.71% throughput difference.

The agent's admitted front door did not expose these files: `Campaign.result`
publishes the request, manifest and worker summary plus timing analysis, not
sample telemetry. The source workbench is scoped to source files. This is an
evidence-access gap, so it would be unfair to attribute the omission solely to
the agent's reasoning. Prefer a bounded, typed, hash-backed telemetry summary
in the CC result over unrestricted filesystem access.

## Measurement limits and correct stopping behavior

The paired source screen measured 13.9698 versus 15.3268 tokens/s, or +9.7133%.
The unchanged 10% gate required 15.3668 tokens/s. Exact tokens, finish reasons,
fixed layer placement and manifest checks passed. The agent did not round up,
claim acceptance, or promote the candidate. The last comparison allowance could
not cover both a new screen and separate confirmation, making its stop sensible.

One AB pair is sensitive to order and cache effects. Raw stderr shows different
cache residency before measured decode: A had 336 of 584 relevant experts
already in RAM, B had 439. Their warmup requests measured about 12.04 and 12.10
tokens/s, respectively. These do not refute the warm measured result, but warn
against treating the gain as solely attributable to the patch. No ABBA was run.
The screen's `baseline_timing_stable=true` is mathematically trivial with one A
process; independent repeatability evidence comes from the earlier two-process
A/A, not that screen flag. Long-context quality and general speedup remain open.

## History and follow-up integration gaps

The original Git handoff preserved report artifact `throughput-goal-final-report`
(SHA256 `84c33a3b40f782073d316e762014722d8ad0382d51ced23200737451672e38e4`).
The terminal decision actually cites `throughput-goal-final-report-v2`
(SHA256 `e01e51eb110cdce3dcb3d7a9f9ad66f54d638ff389e287e68151c3dd156fd321`).
V2 adds the failed methodology-followup interaction. Preserve both and identify
which version is terminal rather than overwriting historical evidence.

The `followup-assessment` observation documents a real semantic mismatch:
`factory.methodology_followup` rejected its text report and requested candidate,
then offered `establish_repeatability` because it did not understand the new
throughput gate shape. The agent correctly rejected that fallback as evidence
against the valid A/A. Fixing report-shape compatibility would prevent wasted
tool calls and misleading proposals; that helper did not submit GPU work.

The history library indexes projected task, decision, observation, evaluation and
attempt records, not artifact contents. It truncates individual strings to 6000
characters and removes environment maps. `experiment_read` cannot recover
omitted content; current-task evidence reads cannot automatically retrieve old
task report artifacts. A raw-file inventory is therefore not enough for a
continuation. Round-2 preparation must expose the verified terminal report and
relevant diagnostics through admitted readable records while retaining original
provenance. The parent reports this report handoff has been added for round 2.

## How to judge round 2

Look for a cited, accurate distinction between rejected prefetch/CPU6 changes
and the promising unconfirmed source patch; a new decision informed by that
distinction; preservation of the original A baseline and exact-output gates;
and reserved capacity for confirmation. Repeating a candidate can be justified
as a declared replication, but must not become repeated screening until a
favorable result appears. If the parallel investigation's new telemetry is
provided to the agent, disclose that assistance: subsequent use demonstrates
learning from shared evidence, not independent discovery of those counters.
