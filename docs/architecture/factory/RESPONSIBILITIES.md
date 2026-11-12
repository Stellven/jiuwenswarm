# M1 → factory responsibilities

The operator-authorized change is recorded in
[DESIGN-CHANGE-2026-11-12.md](DESIGN-CHANGE-2026-11-12.md), under
[AMENDMENT.md](AMENDMENT.md). Historical M1 paths below are relative to
`jiuwenswarm/` at `141c1c4`, read with `git show`; factory paths are relative to
`jiuwenswarm/factory/`. Historical modules remain removed.

| M1 responsibility | M1 file/symbol | Factory file/symbol | Retained behaviour | Changed behaviour | Execution evidence |
|---|---|---|---|---|---|
| Intention compiler | `research/compiler.py:IntentionCompiler.run` | `controller.py:Controller.init_task`; `schemas/task.schema.json`; `store.py:Store.create_task` | Pin objective, constraints, authority, source, budget and evaluation identity as the governing brief. | Operator task inputs form the pinned brief directly; no serial Intent/Requirements agents or compiler restart for each revision. | `<run5:task_id>`, `<run5:contract_id>` |
| Planner | `research/planning.py:PlanningCoordinator.run`, `PlanOutcomeController.record` | Agent decision → `store.py:Store.advance_decision`; `taskgraph.py:plan_patch`; `api.py:dispatch` | Bounded, resource-aware proposals and recorded reasons/outcome lineage. | Agent revises next actions inside the task using evidence. M1's planned rejection could start one linked new run; its frozen run could not revise. No separate planner service. | `<run5:failure_evidence_id>`, `<run5:decision_rev>`, `<run5:graph_rev>` |
| Task graph | `research/binding.py:Binder.freeze`; `research/planning.py:PlanningCoordinator`; `symphony/graph_state.py:GraphStateBuilder.next_state` | `taskgraph.py:plan_patch`, `replay`, `reconcile` | Dependency validation, versioned history and retained identity. Symphony graph state was capability/Skill inventory, distinct from the frozen execution DAG. | Append-only patches revise task work, dependencies, retries, cancellation and supersession. History replays earlier states; this graph carries no dispatch authority and is not a capability inventory. | `<run5:graph_before_rev>`, `<run5:graph_after_rev>`, `<run5:recovery_attempt_id>` |
| Scheduler | `research/scheduler.py:Scheduler.execute_plan` | `jobs.py:Jobs.submit`, `Jobs.status`, `Jobs.cancel`; siminfeng `bin/jobq:worker`, `compatible`; `controller.py:Controller._reconcile` | Resource limits, durable attempt identity, observed outcomes and cancellation. | Frozen serial graph dispatch becomes durable queue execution of chosen actions, with idempotency, restart reconciliation and GPU/build exclusivity. New evidence can justify another action. | `<run5:jobq_id>`, `<run5:recovery_attempt_id>`, `<run5:job_result_evidence_id>` |
| Verifier | `research/compiler.py:VerifierBindings`; `research/binding.py:ContractFactory.prepare_parent` (verifier assignments and gates) | `manager.py:Manager.admit`, `Manager.ingest_upload`; `contract.py:evaluate`; `ab.py:analyse`, `acceptance`; `controller.py:validate_keep_evidence` | Check artifact/image identity, evidence completeness, correctness and acceptance before keeping a component. | Deterministic admission and contract/module acceptance replace mandatory verifier agents and intermediate semantic gates. Acceptance material is pinned per attempt; `keep_component` needs cited accepting evidence. | `<run5:admission_id>`, `<run5:evaluation_id>`, `<run5:keep_decision_rev>` |

The **engine request scheduler** controls inference work inside the engine; it
is a separate responsibility from factory build/lab scheduling through jobq.
The host enforces authority and lifecycle; the agent chooses actions. A plan
patch neither submits a job nor admits an image or changes the scored contract.

## Before/after source map

- Brief and planning: `141c1c4:jiuwenswarm/research/{compiler.py,planning.py}` →
  `jiuwenswarm/factory/{controller.py,store.py,schemas/task.schema.json,taskgraph.py}`
  plus agent decisions.
- Execution and checking: `141c1c4:jiuwenswarm/research/{scheduler.py,binding.py}` →
  `jiuwenswarm/factory/{jobs.py,manager.py,contract.py,ab.py,api.py}` and siminfeng
  `bin/jobq`.
- Graph lineage: `141c1c4:jiuwenswarm/symphony/graph_state.py` →
  `jiuwenswarm/factory/taskgraph.py` for revisable work history; inventory and
  task execution remain different concepts.

The historical policy is
`141c1c4:docs/architecture/design-package/reference/run-plan.md`; current details
are in [TASK-GRAPH.md](TASK-GRAPH.md), [CONTROLLER.md](CONTROLLER.md) and
[MIGRATION.md](MIGRATION.md). Read historical sources only; do not restore them.

Run 5 placeholders above are for the operator to fill from actual recovery
records. They make no measured reliability claim and do not stand in for live
execution evidence.
