# Factory work as a revisable task graph

The factory agent keeps a visible graph of work in `jiuwenswarm/factory/taskgraph.py`.
It is a revisable evidence record. The agent proposes patches from observations;
the host validates them and owns execution authority. Durable jobs remain the
scheduler. Recording a node, including a ready/running node, never submits a job,
changes grants, admits an image, or changes an evaluation contract.

This is the factory-scoped evolution permitted by [AMENDMENT.md](AMENDMENT.md).
It does not import or restore any removed M1 packages.

## M1 concepts and their factory counterparts

Historical paths refer to AI4Research-Main `141c1c4`, inspected with `git show`,
including its `docs/architecture/design-package/platform/planning-and-freeze.md`,
`failure-and-recovery.md`, and `1-system.md`. They are lineage, not dependencies.

| Historical component | M1 concept | Factory counterpart and deliberate change |
|---|---|---|
| `research/planning.py` | Static or planned source selected before execution; bounded proposal checks; `PlanOutcomeController` lineage and a linked compiler follow-up | `taskgraph.initial_plan(task)` suggests proposed work. Agent decisions justify append-only graph patches. CAS revisions retain lineage inside the same task; no compiler restart or frozen plan source. |
| `research/unified_planning.py` | Protected workflow alternatives, graph placement obligations and planner instructions over the accepted Brief/catalog | `taskgraph` validates kinds, dependencies, acyclicity and evidence obligations. The agent chooses additions, retries, cancellations, owners and ordering from the operator task and evidence. No fixed seven-stage workflow. |
| `research/capability_planning.py` | Policy for a bounded capability DAG and compatible workflow shapes | Node `capability` records an optional CC id plus capability. Existing CC-v2 discovery, receipts, task grants and Manager checks govern actual use. The graph carries no new authority. |
| `research/planner_catalog.py`, `research/capsules/planner.py` | Captured immutable declaration catalog; bounded native planner proposal; independent checking before binding/freezing | Existing native factory capsules expose `plan_get`/`plan_patch` alongside evidence. The same decision-making agent revises its work graph. No planner capsule, registry, Binder or generated execution code is introduced. |
| `research/scheduler.py` | Serial frozen-plan execution through SwarmFlow, accepted predecessor gates and bound inputs | Dependency completion produces an advisory frontier. The agent chooses a bounded CC operation; `controller.py`, `jobs.py` and the durable job queue enforce lifecycle. One-shot `taskgraph.reconcile` projects stored attempt outcomes; no graph execution loop or polling service. |
| `research/pi_task.py` | Operator-authored frozen Pi task materials and scorer inputs | Factory tasks retain operator objective, constraints, source, contract and budget. The initial graph is a pure suggestion derived from these inputs; it neither invents measurements nor changes the contract. No Pi pipeline is restored. |
| `symphony/graph_state.py` | Incremental capability/Skill inventory, content and fingerprint hashes, active/removed entries | Task-scoped work nodes carry states, owners, attempt links and evidence links. Cancellation/supersession preserve the original node and every preceding revision. This is work history, not a second capability inventory. |
| `symphony/graph_storage.py` | Versioned graph artifacts published behind a current pointer | Immutable `taskgraph_patch` observations in the existing SQLite evidence store. Contiguous graph revisions replay patches; task scope and `BEGIN IMMEDIATE` CAS protect writes. No filesystem current pointer or separate database. |

M1 bound and froze a DAG before dispatch. The factory keeps a revisable record:
failures can motivate investigation, replacement work, dependency edits and retries.
Host admission, image identity, cancellation confirmation, budgets and scored
evaluation contracts remain enforced by the existing controller/Manager/jobs.
Graph completion is a work-record claim; `accept` still requires the ordinary
decision and evaluation evidence.

## Records, validation and readiness

A graph has `schema: factory.taskgraph/1`, `task_id`, `rev`, `nodes`,
`ready_frontier`, `blocked_reasons`, and decision-linked `history`. Revision zero
is empty. `plan_get(rev=N)` replays only patches through N and returns history
through N. It never reconciles or submits jobs during a read.

Each node has `node_id`, `kind`, `title`, optional `capability`, `inputs` (reference
strings), `depends_on`, `state`, `attempt_ids`, `evidence_ids`,
`created_by_decision_rev`, and `reason`. Superseded nodes also record
`superseded_by`. Kinds are inspect, integrate, build, measure, tune, investigate,
decide, accept and report. States are proposed, ready, running, blocked, done,
failed, cancelled and superseded.

Patches contain lists named `add`, `update`, `cancel`, and/or `supersede`:

- `add` contains new nodes. Creation decision revision is host-controlled.
- `update` names a node and may change `state`, `reason`, or `depends_on`, and
  append `evidence_ids`/`attempt_ids`. The dependency field is a small extension
  to the state/link patch shape so the agent can reorder existing unfinished work.
  Links are retained and deduplicated; retry appends a new attempt ID, last wins.
- `cancel` requires `node_id` and a nonempty `reason`.
- `supersede` requires `node_id`, `by` (an existing or newly added replacement),
  and a nonempty `reason`. It does not silently rewire dependents: the patch
  explicitly updates their `depends_on` fields.

Dependencies must exist and the entire graph must be acyclic. A done node requires
accessible evidence IDs. Running, failed or done build/measure nodes require
attempt IDs from the same task. Proposed, ready or blocked work can precede job
submission, so it need not cite attempts that do not yet exist. Cancelled and
superseded nodes are terminal; replacement work gets a new node ID.

Ready/running/done nodes must have all dependencies done. The frontier contains
proposed or ready nodes with all dependencies done; proposed frontier entries
remain suggestions. Explicitly blocked/failed nodes need an agent revision before
being reconsidered. Blocked reasons name each unfinished dependency, including
cancelled/superseded ones. Cancelling a prerequisite never silently satisfies it.

The controller seeds a proposed inspect → applicability → baseline build →
baseline measurement → integration → candidate build → candidate measurement →
accept → report suggestion when initializing a task. The seed alone cites
decision revision zero and is labelled `origin: seed`. All agent patches must cite
an existing decision revision in that task. Existing tasks without a graph read
as revision zero and are not silently backfilled.

`reconcile_patch(graph, attempts)` is a pure helper for stored durable snapshots;
`reconcile(store, task_id, expected_graph_rev, decision_rev)` reads the task's
attempts and commits at most one patch. Failed jobs become failed work; queued
and running jobs project readiness/running state when dependencies permit.
Success is a done candidate only when the latest attempt's result evidence
exists; evidence retained from an earlier attempt cannot complete a retry.
Otherwise the node is blocked pending evidence. Dependencies are reconciled in
topological order within the same patch. Unknown/cancellation states require agent review.
This function neither polls jobq nor infers success from a missing launcher.
The caller first reconciles jobs through existing lifecycle APIs, then invokes
this helper at the host boundary or records the corresponding agent patch.

## Agent API and atomic decision publication

`factory.evidence` owns `plan_get` and `plan_patch`. A plan is evidence, so sharing
that capsule keeps task scope, native process binding, receipts and persistence
in one existing boundary. A separate `factory.plan` capsule would duplicate those
boundaries without adding execution capability. The existing `run.py` forwards
both calls unchanged; responses use `outputs.plan`. Calls use only local SQLite
and replay, with no model, Docker or network requests. Native round-trip tests
bound the small representative calls to under one second.

```json
{"capability":"plan_get","inputs":{"rev":1}}
```

For separate calls, publish a decision first, then submit its revision together
with the graph revision read by `plan_get`:

```json
{"capability":"plan_patch","inputs":{
  "expected_graph_rev":1,"decision_rev":2,
  "patch":{"add":[{"node_id":"investigate-logs","kind":"investigate",
    "title":"Explain measurement failure","inputs":["measurement-error"],
    "reason":"Failure evidence requires a new approach"}]}
}}
```

For atomic publication, the ordinary decision record MAY include these optional
fields (the outer publish call still supplies `expected_rev`):

```json
{"type":"decision","expected_rev":1,"record":{
  "hypothesis":"Investigate the failed measurement before replacing integration",
  "evidence_ids":["measurement-error"],
  "plan_patch":{"add":[{"node_id":"investigate-logs","kind":"investigate",
    "title":"Explain measurement failure","inputs":["measurement-error"]}]},
  "expected_graph_rev":1
}}
```

Both optional fields must appear together. The decision and patch commit in one
Store transaction, or both roll back on either stale CAS, validation error or
persistence failure. Historical decisions have null optional fields. No broad
controller rewrite is needed: the hook is in `Store.advance_decision`.
Agent observation publication cannot forge reserved `taskgraph_patch` records.
Read grants never confer graph writes to another task.

After a committed patch, telemetry emits `factory.telemetry/1` with
`event: plan.patch`, `graph_rev`, `decision_rev`, `origin`, operation counts and
the redacted patch. Failed transactions emit no plan revision. Existing evidence
exports include graph observations and decision patch fields, so bundle readers
can replay the same history without another manifest or service.

## Example revision after failure

Suppose graph revision 4 contains completed inspection/baseline work, an
integration `integrate-v1`, and measurement `measure-v1` linked to `attempt-7`.
The job fails and its result evidence is `measurement-error`. Decision 6 explains
the failure and publishes this patch against graph revision 4:

```json
{
  "update":[{"node_id":"measure-v1","state":"failed",
    "attempt_ids":["attempt-7"],"evidence_ids":["measurement-error"]}],
  "add":[
    {"node_id":"investigate-logs","kind":"investigate",
     "title":"Explain measurement failure","depends_on":["baseline-measure"],
     "inputs":["measurement-error"]},
    {"node_id":"integrate-v2","kind":"integrate","title":"Apply evidence-led repair",
     "depends_on":["investigate-logs"]}
  ],
  "supersede":[{"node_id":"integrate-v1","by":"integrate-v2",
    "reason":"Measurement failure invalidated the prior integration approach"}]
}
```

Revision 5 preserves `attempt-7`, the failed measurement and the superseded
integration. Investigation becomes the next frontier; replacement integration
waits for it. A later decision can add a new measurement and explicitly rewire
accept/report work. Reading revision 4 still shows exactly the old graph.

## Inspection and merge boundaries

```sh
jiuwenswarm factory --home /path/to/factory plan TASK
jiuwenswarm factory --home /path/to/factory plan TASK --rev 2 --json
jiuwenswarm factory --home /path/to/factory plan TASK --dot
```

Text prints the dependency tree, states, blocked reasons, frontier and revision
history. DOT prints dependency edges, replacement links and decision history in
comments. JSON returns the full graph. Reads use the existing read-only story
snapshot discipline, including bundle support. `render_text(graph)` and
`to_json(graph)` are available to other views. Story appends the text graph;
the monitor exposes `/api/plan?task=TASK` and a collapsible plan panel.

Shared controller edits are limited to the guarded optional seed import and a
seed call after task creation. Story has one rendering hook and monitor one API
branch; agent instructions have a short plan paragraph. Manager, components and
component directories are untouched. The operator should retain these hooks when
merging concurrent controller/view changes; all graph behavior stays in the new
module. No live agent, build, image or GPU run is claimed by the offline tests.
