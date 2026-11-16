# Agent-driven native throughput campaigns

The operator requested a real goal-driven run on 2026-11-16: improve tokens/s,
consult prior experiments, plan the workflow, execute it, revise it from evidence,
and report the achieved result. The initial bounded goal is a 10% improvement in
decode tokens/s on the fixed-placement STRATA modification, not a smoke test.

## Agent and workflow integration

The existing JiuwenSwarm factory controller remains the decision-loop host. A
task with `resources.native_workflow_config` selects the native workflow MCP
front door. This adds workflow catalog/create/append/tick/get/stop and experiment
search/read tools alongside the existing CC tools. The model chooses graph
composition and interventions. Native CC execution and Lab Manager own jobs;
there is no second scheduler or permanent Stage-to-CC adapter.

The controller waits while durable work runs. On its next turn the agent collects
the same graph's results, records a decision, and appends justified work. Source
inspection and edits use the existing source-workbench CC. Custom initial and
appended definitions can only compose operator-selected capabilities. The graph
cannot expand grants or change the task. Final acceptance requires cited,
independently reverified confirmation evidence.

## Retained experiment library

`resources.experiment_library` supplies a persistent index root and an explicit
list of source factory databases. Sources are opened read-only. Search refreshes
the index, including the current campaign, so later decisions can consult its
new results. Changed record snapshots are retained instead of overwriting past
states. Search scope remains restricted to the task's admitted source list.

Each result identifies the source database, task, record, table and snapshot hash.
The library indexes bounded projections of tasks, decisions, observations,
evaluations and attempts, including failures and negative findings. Large token
arrays and raw logs stay in their original stores. This is searchable retained
evidence, not an assertion that every historical experiment remains applicable.
Historical prose never changes current instructions, grants or acceptance rules.
New campaign preparation must include its database in the admitted source list.

The first campaign connected 15 existing/current stores and indexed 554 initial
snapshots. Its persistent index is on Spark at
`/home/user2/software-factory-spark-20261113/experiment-library`.

## Throughput capsule

`factory.throughput_campaign` is a native CC with submit/status/result/cancel.
The operator freezes baseline image, workload, allowable runtime settings,
target gain, resource limits and total GPU process budget. A source candidate
must provide a successful same-task native build receipt; the host resolves and
admits its immutable image. The agent cannot select arbitrary images or rewrite
the evaluator.

Stages are fresh A/A qualification, paired A/B exploration, then separate A-B-B-A
confirmation for an unchanged positive candidate. Every process performs one
unscored warmup and one measured request. Independent analysis verifies raw
hashes, container boundaries, actual replay, model inventory, six-expert
engagement, all 40 fixed-placement layer identities, exact output tokens and
finish reasons before using timings. The slowest candidate must meet the target
against the fastest baseline in confirmation; baseline spread is bounded. No
population confidence interval, general accuracy score or automatic promotion
is implied by this small frozen-workload comparison.

GPU process allowances include cancelled and failed comparisons and are reserved
under a campaign admission lock. History and result collection cannot grant new
GPU work. The ordinary shared queue, process guards and exact-owned-container
cleanup remain authoritative. A rejected candidate is retained, not erased or
retrofitted with a weaker contract.

## First live request

The task is `native-throughput-goal-001`; the model-created graph is
`throughput-goal`. Its files are under
`/home/user2/software-factory-spark-20261113/native-throughput-goal-20261116`.
The live console on port 5175 is scoped to this task. Limits are two hours,
18 agent turns, three native source builds, five comparison jobs and twelve GPU
processes. The frozen workload uses a 1471-token prompt with 64 output tokens,
full six experts and a fixed 76 GB expert-placement budget. The source baseline
is `89ae0ee6123597636ef162dec826230186c00f3b`.

## Observed outcome, 2026-11-16

The actual JiuwenSwarm/Codex agent completed the request with
`report_inconclusive`. It read and cited historical experiments, created the
workflow before execution, revised it to revision 18, rejected two runtime
hypotheses, edited STRATA source, built it natively and measured it on the GPU.

| Candidate | Paired baseline tokens/s | Candidate tokens/s | Observed gain |
| --- | ---: | ---: | ---: |
| Expert lookahead enabled | 13.9149 | 12.9277 | -7.09% |
| Six CPU workers | 14.0022 | 13.9510 | -0.37% |
| ARM64 idle spin reduced from 20ms to 200us | 13.9698 | 15.3268 | +9.71% |

All exact-output and placement checks passed. None met the frozen 10% screen
gate, so no ABBA confirmation or candidate promotion occurred. The last result
is exploratory and does not establish a repeatable speedup. Eight GPU processes,
four comparisons and one source build were consumed. One comparison allowance
remained, insufficient for both another screen and confirmation. The agent
explicitly stopped the collected graph; its API status is `cancelled`, with all
18 nodes completed and no cleanup pending. This was an orderly campaign stop,
not a failed GPU execution.

The persistent library now contains 578 snapshots across 15 stores, including
the current decisions and negative measurements. The final report is retained
as a verified artifact in the current store; raw evidence stays on Spark.

- [Unedited agent report](qualifications/20261116-throughput-agent-report.md)
- [Independently reverified measurements and provenance](qualifications/20261116-throughput-agent.json)
- [Unpromoted agent-authored STRATA patch](qualifications/20261116-strata-arm64-idle-spin.patch)

The factory source changes passed 57 distinct focused Python checks (56 in the
combined run plus one later admission case); the real MCP preflight exposed 16
tools. Post-run verification reparsed all four comparisons, checked raw hashes
and exact boundaries, and confirmed GPU cleanup. The live console loaded the
18-node graph, exposed collected evidence and replayed recorded events without
changing the event log or producing browser errors. Its default five-second
browser assertion was insufficient for this larger graph over SSH; the bounded
60-second retry passed. Graph rendering currently presents literal-input leaves
without data-flow edges; revision evidence retains their causal ordering.

The next justified experiment is to measure CPU scheduling/throttling and wake
latency before selecting a follow-up intervention, then run a newly budgeted AA,
screen and unchanged-candidate ABBA campaign. Keep the threshold unchanged.

Model files, dependency bundles, the index, raw logs and mutable stores remain
outside Git. Completed runs remain readable after execution authority expires.
