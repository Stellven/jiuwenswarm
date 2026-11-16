# Native CC workflows on DGX Spark

The native service passed bounded GPU execution qualification and is active on
Spark port 5175. See the [service runbook](SPARK-NATIVE-SERVICE.md) and
[2026-11-16 qualification record](qualifications/20261116-spark-native.json)
for scope, evidence, task limits and rollback.
The subsequent [agent-driven throughput campaign](NATIVE-THROUGHPUT-AGENT.md)
connects the actual decision maker to this graph runtime and retained experiment
history; build/inference smoke qualification alone did not exercise that loop.

## Application and ownership

The application is an iterative inference-engine software factory on DGX Spark.
STRATA is the reference workload and source baseline, not the orchestration
architecture. The objective is to construct source, build an engine, independently
evaluate it, retain evidence, and choose the next bounded investigation. A rejected
candidate can be a successful factory cycle. Never infer a speedup from graph
completion, source generation, a build, or a recorded presentation.

The multiworkflow team owns composition, adaptive graph revisions, scheduling and
graph/replay presentation. The CC/Lab Manager team owns capability contracts,
sealed implementation identities, invocation receipts, task authority, durable
job admission, budgets, resource lifecycle and independent evaluation. Shared
changes concern these interfaces and application acceptance. There is no new
stage-to-CC executable adapter. `Capability` is a read-only description of a
sealed CC; only `Host.call` executes it.

This integration starts at Spark `eea97929c610aff40e6201aea6d13a2df2a6a776`
and imports `dynamical-workflow` at
`73da54106ba56bd856c1074b05ff17eb8de4d2fb`. Existing source workbench, builder,
lab and evidence capsules remain native CC v2 packages. The incoming Ascend
source-generation example is retained for comparison, not required for Spark
acceptance. M1 services remain removed.

## Execution contract

- Workflow definitions reuse the incoming typed port composition model, extended
  to nested reusable subworkflows with cycle/depth checks. A selected internal
  workflow executes its dependency closure without replaying its siblings.
- Configuration selects immutable releases. Graph requests cannot grant effects,
  change task identity, choose arbitrary executables or reseal a package.
- A persisted invocation intent precedes dispatch. Its key binds run and leaf;
  restart uses the same key. An unknown CC result remains unknown until the host
  reconciles it. A new key is a new attempt, never implicit recovery.
- The graph ledger lives in a separate SQLite database. It retains graph revisions,
  exact call receipts and task/attempt links. Lab Manager remains the sole owner of
  resource admission and durable jobs. Its existing campaign budgets still apply;
  `max_nodes` is an additional composition bound, not a GPU budget.
- Builder/lab submission acknowledgements wait for status and result collection.
  The equivalent inference-lab, integration-skill and expert-streaming aliases
  share that lifecycle. Old factory-loop scheduler operations and submission
  interfaces lacking a supported cancellation lifecycle are not exposed as
  native workflow leaves; their packages remain intact for the old entrypoint.
  The standard benchmark CC now includes scoped cancellation (version 1.1.0),
  so independently admitted source comparisons can use the same native lifecycle.
  Its wrapped `result` output remains unchanged; orchestration retains the original
  CC output envelope and separately tracks the owned attempt.
  Results are collected after failure/cancellation too. Independent branches keep
  progressing when a different branch's cancellation fails. Pending/unknown jobs
  cannot produce completed descendants.
- Stop prevents unclaimed dispatch and reconciles already claimed work. Physical
  cleanup is separate: `cleanup_pending` and `cancellation_complete` are explicit.
  Existing `containers_unverified` cleanup is never upgraded to proven cleanup;
  shutdown then reports `needs_reconciliation`. Do not use that status as a clean
  hardware handoff.
- Adaptation appends new instances under an expected revision, with a reason and
  task-scoped collected-node evidence. It cannot rewrite an existing attempt or
  widen the operator's release/grant set. The agent decides; the runtime does not
  select an optimization policy.
- Graph completion leaves `acceptance=not_assessed`. The actual scientific verdict
  lives in the independently collected lab evaluation. Artifact integrity and CC
  schema validity are not scientific validation.

## Running it

Use Linux for factory capsules. Start with an already admitted task, fresh bounded
campaign constraints, and its task-owned source checkout. Do not revive an expired
campaign or migrate a live store. Preserve `FACTORY_HOME`, `FACTORY_TASK_ID`,
`FACTORY_WORKSPACE`, the selected factory Python and dependency/source environment
for the lifetime of the service. One service process is scoped to one task; no
request changes global environment variables.

Prepare selected existing packages once, outside the repository's tracked tree:

```sh
python -m jiuwenswarm.software_factory.cc_prepare \
  --config /path/to/task/workflow-config.json --task-id "$FACTORY_TASK_ID" \
  --package jiuwenswarm/factory/ccs/source_workbench \
  --package jiuwenswarm/factory/ccs/builder \
  --package jiuwenswarm/factory/ccs/lab_client \
  --grant process.exec --grant workspace.write
python -m jiuwenswarm.software_factory.cli \
  --config /path/to/task/workflow-config.json catalog
```

Only supply grants already authorized for the task. Preparation writes reusable
leaf workflows; orchestration can compose those into subworkflows or submit an
append-only revision using `CCService.append`. Optional ports can be bound in a
custom composition. Calls that submit jobs receive graph-owned idempotency keys.
Preserve source/build receipt/image identities in the actual builder/lab inputs.

Create a JSON request containing `workflow`, `objective`, `inputs`, and optionally
`run_id`. Then use the native CLI commands `create request.json`, `run RUN_ID
--seconds 60`, `get RUN_ID`, `events RUN_ID`, `append RUN_ID revision.json`, or
`stop RUN_ID`. `run` advances for a bounded interval; stopping that CLI does not
cancel admitted lab work. Explicit `stop` plus continued `run` reconciles children.

For the existing web host, set `JIUWENSWARM_CC_WORKFLOW_CONFIG` to the configuration
path. The Software Factory panel is now the native CC view. Its API is
`/api/v1/cc-workflows`; it is available to the local operator connection only.
Use the existing SSH tunnel when operating Spark remotely. Host port remains
5175. The UI provides explicit run/resume, stop, graph/evidence inspection, and
read-only event replay. Replay never executes capabilities.

## Compatibility and qualification

The old source-production executor is temporarily available only through
`cli --example` or `JIUWENSWARM_FACTORY_EXAMPLE=1`; its UI additionally requires
`?factoryExample=1`. This is a rollback/example lane, not a second Spark scheduler.
Retire it after the orchestration owner ports any additional useful source
construction primitives into native CCs and accepts the integrated demo.

Required release gates are: native composition/recovery/fault tests; real Linux
source-workbench transport; existing factory regression tests; frontend build and
replay inspection; then a fresh bounded Spark build and independent baseline/candidate
evaluation using the admitted construction-comparison contracts. The Spark numerical
replay changes at eea97929c still require a newly built CUDA capture and independently
pinned input qualification. Historical results and the incoming Ascend replay do not
satisfy that gate. Keep archives, models, mutable stores and large run artifacts out
of Git; retain small source changes, contracts, evidence references and qualification
summaries.
